from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "rag_phase2_review_unlock_estimator.py"
OFFICIAL_DENOMINATOR = ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"


def test_phase2_estimator_generates_valid_json_and_preserves_inputs(tmp_path):
    module = _load_module()
    inputs = _fixture_inputs(tmp_path)
    before_hashes = {
        "enriched": _sha256(inputs["enriched_csv"]),
        "review": _sha256(inputs["review_required_csv"]),
        "official": _sha256(OFFICIAL_DENOMINATOR) if OFFICIAL_DENOMINATOR.exists() else "",
    }

    payload = module.run_estimator(**inputs, output_dir=tmp_path / "out")
    module.write_outputs(tmp_path / "out", payload)

    generated = tmp_path / "out" / "phase2_review_unlock_estimate.json"
    loaded = json.loads(generated.read_text(encoding="utf-8"))

    assert loaded["schema_version"] == "rag_phase2_review_unlock_estimate_v1"
    assert _sha256(inputs["enriched_csv"]) == before_hashes["enriched"]
    assert _sha256(inputs["review_required_csv"]) == before_hashes["review"]
    if OFFICIAL_DENOMINATOR.exists():
        assert _sha256(OFFICIAL_DENOMINATOR) == before_hashes["official"]
    assert loaded["guardrail_status"]["official_denominator_registry_changed"] is False


def test_default_output_directory_is_ignored_temporary_output():
    module = _load_module()
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert module.DEFAULT_OUTPUT_DIR == REPO_ROOT / ".tmp" / "phase2-review-unlock"
    assert module.DEFAULT_OUTPUT_DIR != module.DEFAULT_DOCS_DIR
    assert ".tmp/" in gitignore_text


def test_generated_artifacts_do_not_require_docs_directory(tmp_path):
    module = _load_module()
    out_dir = tmp_path / "diagnostic-out"
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=out_dir)
    module.write_outputs(out_dir, payload)

    for filename in module.REPORT_OUTPUTS.values():
        assert (out_dir / filename).exists()
        assert not (tmp_path / "docs" / filename).exists()
    assert all("diagnostic-out" in path for path in payload["outputs"].values())


def test_row_and_canonical_denominators_and_lane_mappings_are_reported(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")

    retrieval = payload["denominators"]["rag_retrieval_core"]
    visual = payload["denominators"]["visual_shadow"]

    assert retrieval["row_level"]["denominator"] == 8
    assert retrieval["canonical_level"]["denominator"] == 8
    assert retrieval["row_level"]["metrics"]["vector_db_internal_allowed"]["numerator"] == 2
    assert "vector_readiness" in retrieval["row_level"]
    assert "vector_readiness" in retrieval["canonical_level"]
    assert visual["row_level"]["denominator"] == 3
    assert visual["canonical_level"]["denominator"] == 3
    assert visual["row_level"]["metrics"]["vector_db_internal_allowed"]["numerator"] == 0
    assert payload["scope_definitions"]["rag_retrieval_core"]["lane_mapping_status"].startswith("detected")
    assert payload["scope_definitions"]["visual_shadow"]["lane_mapping_status"].startswith("detected")


def test_phase2b_derived_views_keep_official_and_promotion_scope_separate(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    views = payload["derived_readiness_views"]

    official = views["official_denominator_readiness"]["rag_retrieval_core"]["row_level"]
    promotion = views["promotion_scope_readiness"]["rag_retrieval_core"]["row_level"]

    assert official["current_denominator"] == 8
    assert official["current_numerator"] == 2
    assert official["after_conservative_unlock_numerator"] == 6
    assert official["new_all_qualified_units_needed_after_conservative_unlock"] == 2

    assert promotion["current_denominator"] < official["current_denominator"]
    assert promotion["current_numerator"] == 1
    assert promotion["after_conservative_unlock_numerator"] == 5
    assert promotion["new_all_qualified_units_needed_after_conservative_unlock"] == 0


def test_license_first_source_family_policy_classifications(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    by_family = {item["source_family_id"]: item for item in payload["source_family_priorities"]}

    assert by_family["PUBLIC_DATA_PORTAL"]["classification"] == "REVIEW_FIRST"
    assert by_family["SEOUL_OPEN_DATA"]["classification"] == "REVIEW_FIRST"
    assert by_family["FUNSD"]["classification"] == "DIAGNOSTIC_ONLY"
    assert by_family["HUGGING_FACE"]["classification"] == "REVIEW_FIRST"
    assert by_family["KOSIS"]["classification"] == "COLLECT_NOW"

    namu = by_family["NAMU"]
    assert namu["classification"] == "DIAGNOSTIC_ONLY"
    assert namu["policy_posture"] == "NONCOMMERCIAL_LIMITED"
    assert namu["public_release_allowed_rows"] == 0
    assert namu["support_eligible_rows"] == 0
    assert namu["gold_candidate_allowed_rows"] == 0

    assert by_family["PRISM"]["classification"] == "DIAGNOSTIC_ONLY"
    assert by_family["PUBLIC_INSTITUTION"]["classification"] == "DIAGNOSTIC_ONLY"
    assert by_family["DART"]["classification"] == "REVIEW_FIRST"
    assert by_family["DART"]["vector_db_internal_allowed_rows"] == 0


def test_diagnostic_drag_excludes_funsd_from_visual_promotion_scope(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    views = payload["derived_readiness_views"]
    visual_drag = {
        item["source_family_id"]: item
        for item in views["diagnostic_drag_breakdown"]["visual_shadow"]
    }

    assert visual_drag["FUNSD"]["row_denominator_drag"] == 1
    assert visual_drag["FUNSD"]["row_promotion_scope_denominator"] == 0
    assert views["promotion_scope_readiness"]["visual_shadow"]["row_level"]["current_denominator"] == 0


def test_namu_vector_readiness_promotion_block_warning(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    warnings = payload["derived_readiness_views"]["vector_readiness_promotion_block_warnings"]

    namu_warnings = [warning for warning in warnings if warning["source_family_id"] == "NAMU"]
    assert namu_warnings
    assert namu_warnings[0]["warning"] == "counted_in_vector_readiness_but_blocked_from_public_support_gold_promotion"


def test_unsafe_license_rows_are_not_effectively_promoted(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    guardrails = payload["guardrail_status"]

    assert guardrails["unsafe_license_effective_vector_eligible_count"] == 0
    assert guardrails["unsafe_license_effective_public_release_count"] == 0
    assert guardrails["unsafe_license_effective_support_eligible_count"] == 0
    assert guardrails["unsafe_license_effective_gold_candidate_count"] == 0
    assert guardrails["raw_unsafe_license_vector_flag_count"] >= 2


def test_collect_now_requires_safe_public_data_status(tmp_path):
    module = _load_module()
    inputs = _fixture_inputs(tmp_path, kosis_bad=True)
    payload = module.run_estimator(**inputs, output_dir=tmp_path / "out")
    by_family = {item["source_family_id"]: item for item in payload["source_family_priorities"]}

    assert by_family["KOSIS"]["classification"] == "REVIEW_FIRST"
    assert (
        module.item_level_evidence_captured(
            {
                "license_status": "VERIFIED_OPEN_PUBLIC_DATA",
                "source_license_evidence_field": "configured_source_family_rule",
                "license_verification_method": "configured_source_terms_page",
            }
        )
        is False
    )


def test_kosis_mixed_state_is_explicit_for_source_family_terms(tmp_path):
    module = _load_module()
    inputs = _fixture_inputs(tmp_path, kosis_source_family_only=True)
    payload = module.run_estimator(**inputs, output_dir=tmp_path / "out")
    state = payload["derived_readiness_views"]["kosis_state"]
    by_family = {item["source_family_id"]: item for item in payload["source_family_priorities"]}

    assert by_family["KOSIS"]["classification"] == "REVIEW_FIRST"
    assert state["vector_stage_eligible"]["rows"] == 1
    assert state["support_eligible"]["rows"] == 0
    assert state["gold_candidate_allowed"]["rows"] == 0
    assert state["license_evidence_level"] == "source_family_or_terms_page_only"
    assert "source_family_terms_only_requires_item_level_or_equivalent_evidence" in state["review_required_reason"]


def test_promotion_scope_rag_zero_denominator_rate_is_null(tmp_path):
    module = _load_module()
    inputs = _fixture_inputs(tmp_path, kosis_source_family_only=True)
    payload = module.run_estimator(**inputs, output_dir=tmp_path / "out")
    promotion = payload["derived_readiness_views"]["promotion_scope_readiness"]["rag_retrieval_core"]

    assert promotion["row_level"]["current_denominator"] == 0
    assert promotion["row_level"]["current_rate"] is None
    assert promotion["row_level"]["current_rate_status"] == "no_currently_eligible_promotion_scope_units"

    report = module.render_estimate_md(payload)
    assert "`0/0 = N/A`" in report
    assert "no_currently_eligible_promotion_scope_units" in report


def test_generated_report_content_stays_aggregate_only(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    report = module.render_estimate_md(payload)

    for rawish_value in [
        "fixture_manifest.csv",
        "Do Not Surface Row Title",
        "canon_namu",
        "unsafe_raw_flags",
        "row_license",
        "row_catalog_license",
    ]:
        assert rawish_value not in report


def test_annotation_and_ocr_mm_support_guardrails_stay_zero(tmp_path):
    module = _load_module()
    payload = module.run_estimator(**_fixture_inputs(tmp_path), output_dir=tmp_path / "out")
    guardrails = payload["guardrail_status"]

    assert guardrails["annotation_answer_embedding_count"] == 0
    assert guardrails["support_eligible_ocr_mm_count"] == 0
    assert guardrails["hidden_xlsx_exposed"] is False
    assert guardrails["promotion_evidence"] is False


def _load_module():
    spec = importlib.util.spec_from_file_location("rag_phase2_review_unlock_estimator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_inputs(
    tmp_path: Path,
    *,
    kosis_bad: bool = False,
    kosis_source_family_only: bool = False,
) -> dict:
    enriched_csv = tmp_path / "existing_manifest_license_enriched.csv"
    review_csv = tmp_path / "license_review_required_rows.csv"
    rows = _fixture_rows(kosis_bad=kosis_bad, kosis_source_family_only=kosis_source_family_only)
    _write_csv(enriched_csv, rows)
    _write_csv(review_csv, [row for row in rows if row["requires_user_license_review"] == "true"])

    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    readiness_md = report_dir / "existing_manifest_experiment_readiness.md"
    summary_md = report_dir / "existing_manifest_license_summary_by_source.md"
    usage_md = report_dir / "existing_manifest_license_usage_gate.md"
    readiness_md.write_text("# readiness\n", encoding="utf-8")
    summary_md.write_text("# summary\n", encoding="utf-8")
    usage_md.write_text("# usage\n", encoding="utf-8")

    phase1_dir = tmp_path / "phase1"
    phase1_dir.mkdir()
    for filename in [
        "phase1_visual_shadow_source_summary.csv",
        "phase1_review_license_status_summary.csv",
        "phase1_retrieval_core_source_summary.csv",
        "phase1_lane_readiness_summary.csv",
        "phase1_source_family_readiness_summary.csv",
    ]:
        _write_csv(phase1_dir / filename, [{"source_family_id": "FIXTURE", "rows": "1"}])
    (phase1_dir / "phase1_csv_reanalysis.md").write_text("# phase1\n", encoding="utf-8")

    return {
        "enriched_csv": enriched_csv,
        "review_required_csv": review_csv,
        "readiness_md": readiness_md,
        "summary_by_source_md": summary_md,
        "usage_gate_md": usage_md,
        "phase1_dir": phase1_dir,
    }


def _fixture_rows(
    *,
    kosis_bad: bool = False,
    kosis_source_family_only: bool = False,
) -> list[dict[str, str]]:
    base = {
        "subtype": "",
        "role": "",
        "title": "Do Not Surface Row Title",
        "relative_path": "",
        "sha256": "",
        "source_page": "",
        "download_url": "",
        "source_license_evidence_field": "",
        "license_verification_method": "",
        "license_notes": "",
        "promotion_evidence": "false",
        "internal_eval_allowed": "false",
        "embedding_allowed": "false",
        "vector_db_internal_allowed": "false",
        "ocr_processing_allowed": "false",
        "vlm_processing_allowed": "false",
        "parser_smoke_required": "false",
        "public_release_allowed": "false",
        "support_eligible": "false",
        "gold_candidate_allowed": "false",
        "annotation_answer_embedding_allowed": "false",
        "pdf_file_identity_only": "false",
        "split_group_key": "",
    }

    def row(row_id: str, **updates: str) -> dict[str, str]:
        item = dict(base)
        item.update(
            {
                "manifest_source_path": "fixture_manifest.csv",
                "row_id": row_id,
                "canonical_row_id": f"canon_{row_id}",
                "source_domain": "",
                "source_family_id": "UNKNOWN_SOURCE",
                "license_status": "UNKNOWN_NEEDS_REVIEW",
                "requires_user_license_review": "true",
                "intended_experiment_use": "HOLD_LICENSE_UNKNOWN",
            }
        )
        item.update(updates)
        return item

    kosis_status = "SOURCE_LICENSE_NOT_FOUND" if kosis_bad else "VERIFIED_OPEN_PUBLIC_DATA"
    kosis_review = "true" if kosis_bad else "false"
    kosis_vector = "false" if kosis_bad else "true"
    kosis_evidence_field = "configured_source_family_rule" if kosis_source_family_only else "row_license"
    kosis_verification_method = "configured_source_terms_page" if kosis_source_family_only else "row_catalog_license"
    return [
        row(
            "data",
            lane="XLSX",
            source_family_id="PUBLIC_DATA_PORTAL",
            source_domain="www.data.go.kr",
            license_status="LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED",
            internal_eval_allowed="true",
            parser_smoke_required="true",
            intended_experiment_use="HOLD_LICENSE_AMBIGUOUS",
        ),
        row(
            "seoul",
            lane="PDF_CONTENT",
            source_family_id="SEOUL_OPEN_DATA",
            source_domain="data.seoul.go.kr",
            license_status="LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED",
            internal_eval_allowed="true",
            parser_smoke_required="true",
            intended_experiment_use="HOLD_LICENSE_AMBIGUOUS",
        ),
        row(
            "funsd",
            lane="OCR_IMAGE",
            source_family_id="FUNSD",
            source_domain="guillaumejaume.github.io",
            license_status="VERIFIED_RESEARCH_ONLY",
            internal_eval_allowed="true",
            ocr_processing_allowed="true",
            vlm_processing_allowed="true",
            intended_experiment_use="READY_INTERNAL_NONCOMMERCIAL_OCR_MM_EXPERIMENT",
        ),
        row(
            "namu",
            lane="TEXT_NAMU",
            source_family_id="NAMU",
            source_domain="namu.wiki",
            license_status="VERIFIED_NONCOMMERCIAL_ONLY",
            internal_eval_allowed="true",
            embedding_allowed="true",
            vector_db_internal_allowed="true",
            intended_experiment_use="READY_INTERNAL_NONCOMMERCIAL_RAG_EXPERIMENT",
        ),
        row(
            "prism",
            lane="PDF_CONTENT",
            source_family_id="PRISM",
            source_domain="www.prism.go.kr",
            license_status="SOURCE_LICENSE_NOT_FOUND",
            parser_smoke_required="true",
        ),
        row(
            "public_institution",
            lane="XLSX",
            source_family_id="PUBLIC_INSTITUTION",
            source_domain="www.acrc.go.kr",
            license_status="SOURCE_LICENSE_NOT_FOUND",
            parser_smoke_required="true",
        ),
        row(
            "dart",
            lane="PDF_CONTENT",
            source_family_id="DART",
            source_domain="dart.fss.or.kr",
            license_status="SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
            internal_eval_allowed="true",
        ),
        row(
            "kosis",
            lane="XLSX",
            source_family_id="KOSIS",
            source_domain="kosis.kr",
            license_status=kosis_status,
            requires_user_license_review=kosis_review,
            internal_eval_allowed="true",
            embedding_allowed=kosis_vector,
            vector_db_internal_allowed=kosis_vector,
            parser_smoke_required="true",
            source_license_evidence_field=kosis_evidence_field,
            license_verification_method=kosis_verification_method,
            intended_experiment_use="READY_INTERNAL_NONCOMMERCIAL_RAG_EXPERIMENT",
        ),
        row(
            "hf",
            lane="OCR_ANNOTATION",
            source_family_id="HUGGING_FACE",
            source_domain="huggingface.co",
            license_status="SOURCE_LICENSE_NOT_FOUND",
            internal_eval_allowed="true",
            ocr_processing_allowed="true",
            annotation_answer_embedding_allowed="false",
            intended_experiment_use="HOLD_LICENSE_UNKNOWN",
        ),
        row(
            "unsafe_raw_flags",
            lane="XLSX",
            source_family_id="UNKNOWN_SOURCE",
            license_status="SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
            vector_db_internal_allowed="true",
            public_release_allowed="true",
            support_eligible="true",
            gold_candidate_allowed="true",
        ),
        row(
            "unsafe_visual_raw_flags",
            lane="OCR_IMAGE",
            source_family_id="UNKNOWN_SOURCE",
            license_status="SOURCE_TERMS_FOUND_BUT_AMBIGUOUS",
            vector_db_internal_allowed="true",
            public_release_allowed="true",
            support_eligible="true",
            gold_candidate_allowed="true",
        ),
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
