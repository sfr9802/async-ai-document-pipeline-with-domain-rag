from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "rag_existing_manifest_license_usage_gate.py"
CONFIG = ROOT / "eval" / "configs" / "existing_manifest_license_usage_gate.yaml"


def test_enriched_manifest_includes_required_fields_and_verified_requires_evidence(tmp_path):
    module = _load_module()
    config = _config(tmp_path, [_manifest(tmp_path, _baseline_rows())])

    payload = module.run_gate(config=config, config_path=tmp_path / "config.yaml")
    module.write_outputs(config, payload)

    rows = payload["enriched_rows"]
    assert rows
    assert all(field in rows[0] for field in module.OUTPUT_FIELDS)
    assert payload["counts"]["total_rows"] == len(_baseline_rows())
    assert (tmp_path / "review" / "existing_manifest_license_enriched.json").exists()
    assert (tmp_path / "reports" / "existing_manifest_license_usage_gate.json").exists()

    with pytest.raises(ValueError, match="verified license lacks explicit evidence"):
        module.ensure_verified_has_evidence(module.base_decision("VERIFIED_OPEN_LICENSE", "LOW"))


def test_unknown_and_blocker_rows_are_excluded_from_vector_and_public_artifacts(tmp_path):
    module = _load_module()
    rows = [
        _row("unknown", lane="XLSX", title="No source or license", relative_path="a.xlsx"),
        _row(
            "restricted",
            lane="PDF_CONTENT",
            title="Restricted report",
            relative_path="b.pdf",
            source_page="https://example.test/restricted",
            license_note="Restricted terms prohibit third party transfer and redistribution.",
        ),
        _row(
            "public_false",
            lane="XLSX",
            title="Noncommercial row",
            relative_path="c.xlsx",
            source_page="https://example.test/nc",
            license_note="License: CC BY-NC-SA 4.0",
        ),
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    by_id = {row["row_id"]: row for row in payload["enriched_rows"]}

    assert by_id["unknown"]["license_status"] == "UNKNOWN_NEEDS_REVIEW"
    assert by_id["unknown"]["vector_db_internal_allowed"] is False
    assert by_id["unknown"]["intended_experiment_use"] == "HOLD_LICENSE_UNKNOWN"

    assert by_id["restricted"]["license_status"] == "VERIFIED_RESTRICTED"
    assert by_id["restricted"]["redistribution_allowed"] is False
    assert by_id["restricted"]["public_release_allowed"] is False
    assert by_id["restricted"]["intended_experiment_use"] == "BLOCK_LICENSE_RESTRICTED"

    public_ready = [
        row for row in payload["enriched_rows"] if row["intended_experiment_use"] == "READY_PUBLIC_RELEASE_ALLOWED"
    ]
    assert all(row["public_release_allowed"] is True for row in public_ready)
    assert by_id["public_false"]["public_release_allowed"] is False


def test_noncommercial_rows_can_be_internal_but_not_commercial(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "nc",
            lane="TEXT_NAMU",
            title="Noncommercial metadata",
            relative_path="text/1.json",
            source_page="https://example.test/nc",
            license_note="License: CC BY-NC-SA 4.0",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["license_status"] == "VERIFIED_NONCOMMERCIAL_ONLY"
    assert row["internal_eval_allowed"] is True
    assert row["commercial_use_allowed"] is False
    assert row["noncommercial_use_allowed"] is True


def test_public_domain_or_unrestricted_metadata_becomes_open_public_data(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "public_domain",
            lane="MULTIMODAL_IMAGE",
            title="Public domain image",
            relative_path="img/pd.png",
            source_page="https://commons.wikimedia.org/wiki/File:Example.png",
            license_note="Wikimedia Commons; license=Public domain",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["license_status"] == "VERIFIED_OPEN_PUBLIC_DATA"
    assert row["commercial_use_allowed"] is True
    assert row["public_release_allowed"] is True
    assert row["vector_db_internal_allowed"] is True


def test_revisited_data_go_kr_item_license_policy_is_explicit(tmp_path):
    module = _load_module()
    config = _repo_config_with_tmp_paths(tmp_path, [_manifest(tmp_path, [
        _row(
            "data_go",
            lane="XLSX",
            title="data.go.kr unrestricted item",
            relative_path="xlsx/data_go.xlsx",
            source_page="https://www.data.go.kr/data/15011688/fileData.do",
        )
    ])])
    payload = module.run_gate(config=config, config_path=CONFIG)
    row = payload["enriched_rows"][0]

    assert row["license_status"] == "VERIFIED_OPEN_PUBLIC_DATA"
    assert row["license_verification_method"] == "revisited_data_go_kr_catalog_json_license_field"
    assert row["requires_user_license_review"] is False
    assert row["embedding_allowed"] is True
    assert row["vector_db_internal_allowed"] is True


def test_revisited_huggingface_missing_license_stays_review_required(tmp_path):
    module = _load_module()
    config = _repo_config_with_tmp_paths(tmp_path, [_manifest(tmp_path, [
        _row(
            "docvqa",
            lane="OCR_IMAGE",
            title="DocVQA mirror row",
            relative_path="ocr/docvqa.png",
            source_page="https://huggingface.co/datasets/nielsr/docvqa_1200_examples",
        )
    ])])
    payload = module.run_gate(config=config, config_path=CONFIG)
    row = payload["enriched_rows"][0]

    assert row["license_status"] == "SOURCE_LICENSE_NOT_FOUND"
    assert row["license_verification_method"] == "revisited_huggingface_dataset_api_license_null"
    assert row["requires_user_license_review"] is True
    assert row["vector_db_internal_allowed"] is False
    assert row["public_release_allowed"] is False


def test_no_derivatives_rows_do_not_auto_become_ocr_mm_vector_ready(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "kogl3_ocr",
            lane="OCR_IMAGE",
            title="No derivatives OCR image",
            relative_path="ocr/no_derivative.png",
            source_page="https://example.test/kogl3",
            license_note="공공누리 제3유형 출처표시 + 변경금지",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["license_status"] == "VERIFIED_KOGL_TYPE_3_NO_DERIVATIVES"
    assert row["no_derivatives"] is True
    assert row["ocr_processing_allowed"] is False
    assert row["vlm_processing_allowed"] is False
    assert row["vector_db_internal_allowed"] is False
    assert row["intended_experiment_use"] == "HOLD_NO_DERIVATIVES_OCR_MM_UNCLEAR"


def test_ai_hub_or_restricted_rows_are_not_redistributed(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "aihub",
            lane="OCR_IMAGE",
            title="AI Hub sample",
            relative_path="ocr/aihub.png",
            source_page="https://aihub.or.kr/aihubdata/data/view.do",
            license_note="Research use only. Third party transfer is prohibited.",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["source_family_id"] == "AI_HUB"
    assert row["third_party_transfer_prohibited"] is True
    assert row["redistribution_allowed"] is False
    assert row["public_release_allowed"] is False
    assert row["intended_experiment_use"] == "HOLD_THIRD_PARTY_TRANSFER_PROHIBITED"


def test_ocr_mm_annotations_never_embed_labels_or_become_support(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "ann",
            lane="OCR_ANNOTATION",
            title="OCR annotation",
            relative_path="ocr/ann.json",
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["annotation_answer_embedding_allowed"] is False
    assert row["support_eligible"] is False
    assert row["annotation_allowed_internal"] is True
    assert row["split_group_key"]
    assert payload["guardrail_status"]["annotation_answer_embedding_count"] == 0
    assert payload["guardrail_status"]["support_eligible_ocr_mm_count"] == 0


def test_pdf_file_identity_remains_identity_only(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "pdf_identity",
            lane="PDF_FILE_IDENTITY",
            title="Same title 2025 v1",
            relative_path="pdf/id.pdf",
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        )
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    row = payload["enriched_rows"][0]

    assert row["pdf_file_identity_only"] is True
    assert row["pdf_file_content_mixing_support_allowed"] is False
    assert row["citation_capable_candidate"] is False
    assert row["intended_experiment_use"] == "READY_PDF_FILE_IDENTITY_ONLY"
    assert payload["guardrail_status"]["pdf_file_content_mixing_support_count"] == 0


def test_duplicate_sha_mojibake_and_font_rows_are_blocked(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "dup_a",
            lane="XLSX",
            title="Duplicate A",
            relative_path="x/a.xlsx",
            sha256="0" * 64,
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        ),
        _row(
            "dup_b",
            lane="XLSX",
            title="Duplicate B",
            relative_path="x/b.xlsx",
            sha256="0" * 64,
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        ),
        _row(
            "mojibake",
            lane="PDF_FILE_IDENTITY",
            title="ì„œìš¸ í†µê³„",
            relative_path="pdf/bad.pdf",
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        ),
        _row(
            "font",
            lane="FONT",
            title="Sample font",
            relative_path="fonts/sample.ttf",
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        ),
    ]
    payload = module.run_gate(config=_config(tmp_path, [_manifest(tmp_path, rows)]), config_path=tmp_path / "config.yaml")
    by_id = {row["row_id"]: row for row in payload["enriched_rows"]}

    assert by_id["dup_a"]["duplicate_sha_group_id"]
    assert by_id["dup_b"]["duplicate_sha_group_id"] == by_id["dup_a"]["duplicate_sha_group_id"]
    assert sum(row["intended_experiment_use"] == "HOLD_DUPLICATE_SHA_GROUP_ONLY" for row in by_id.values()) == 1

    assert by_id["mojibake"]["mojibake_identity_risk"] is True
    assert by_id["mojibake"]["vector_db_internal_allowed"] is False
    assert by_id["mojibake"]["intended_experiment_use"] == "HOLD_MOJIBAKE_IDENTITY_RISK"

    assert by_id["font"]["font_user_facing_artifact_allowed"] is False
    assert by_id["font"]["public_release_allowed"] is False
    assert by_id["font"]["intended_experiment_use"] == "HOLD_FONT_NO_USER_FACING_ARTIFACT"


def test_official_denominator_and_production_mutation_guardrails_remain_closed(tmp_path):
    module = _load_module()
    payload = module.run_gate(
        config=_config(tmp_path, [_manifest(tmp_path, _baseline_rows())]),
        config_path=tmp_path / "config.yaml",
    )
    guardrails = payload["guardrail_status"]

    assert guardrails["official_denominator_registry_changed"] is False
    assert guardrails["production_index_mutation"] is False
    assert guardrails["production_vector_write"] is False
    assert guardrails["namespace_created"] is False
    assert guardrails["hidden_xlsx_exposed"] is False
    assert guardrails["promotion_evidence"] is False
    assert guardrails["all_guardrails_preserved"] is True

    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", "ai/eval/eval_queries/official_denominator_registry.json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert diff.returncode == 0


def _load_module():
    spec = importlib.util.spec_from_file_location("rag_existing_manifest_license_usage_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _config(tmp_path: Path, manifests: list[Path]) -> dict:
    return {
        "inputs": {
            "discover_repo_manifests": False,
            "manifest_paths": [str(path) for path in manifests],
            "repo_manifest_globs": [],
            "exclude_path_contains": [],
        },
        "network_verification": {"enabled": False},
        "source_family_policies": [],
        "readiness_thresholds": {
            "retrieval_core_internal_eval_allowed_rate": 0.80,
            "retrieval_core_embedding_allowed_rate": 0.70,
            "retrieval_core_vector_db_internal_allowed_rate": 0.70,
            "xlsx_pdf_content_parser_smoke_candidate_count": 1,
            "visual_shadow_internal_eval_allowed_rate": 0.80,
            "visual_shadow_ocr_or_vlm_processing_allowed_rate": 0.70,
            "visual_shadow_vector_db_internal_allowed_rate": 0.60,
        },
        "outputs": {
            "enriched_json": str(tmp_path / "review" / "existing_manifest_license_enriched.json"),
            "enriched_csv": str(tmp_path / "review" / "existing_manifest_license_enriched.csv"),
            "gate_md": str(tmp_path / "reports" / "existing_manifest_license_usage_gate.md"),
            "gate_json": str(tmp_path / "reports" / "existing_manifest_license_usage_gate.json"),
            "summary_by_source_md": str(tmp_path / "reports" / "existing_manifest_license_summary_by_source.md"),
            "summary_by_source_json": str(tmp_path / "reports" / "existing_manifest_license_summary_by_source.json"),
            "readiness_md": str(tmp_path / "reports" / "existing_manifest_experiment_readiness.md"),
            "readiness_json": str(tmp_path / "reports" / "existing_manifest_experiment_readiness.json"),
            "review_required_csv": str(tmp_path / "review" / "license_review_required_rows.csv"),
        },
    }


def _repo_config_with_tmp_paths(tmp_path: Path, manifests: list[Path]) -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    config["inputs"] = {
        "discover_repo_manifests": False,
        "manifest_paths": [str(path) for path in manifests],
        "repo_manifest_globs": [],
        "exclude_path_contains": [],
    }
    config["outputs"] = _config(tmp_path, manifests)["outputs"]
    return config


def _baseline_rows() -> list[dict[str, str]]:
    return [
        _row(
            "open",
            lane="XLSX",
            title="Open spreadsheet",
            relative_path="x/open.xlsx",
            source_page="https://example.test/open",
            license_note="License: CC BY 4.0",
        )
    ]


def _row(
    row_id: str,
    *,
    lane: str,
    title: str,
    relative_path: str,
    source_page: str = "",
    sha256: str | None = None,
    license_note: str = "",
) -> dict[str, str]:
    row = {
        "row_id": row_id,
        "lane": lane,
        "title": title,
        "relative_path": relative_path,
        "sha256": sha256 or row_id.encode("utf-8").hex().ljust(64, "0")[:64],
        "source_page": source_page,
        "download_url": "",
        "notes": "test row",
        "collected_at": "2026-05-10T00:00:00+09:00",
    }
    if license_note:
        row["license_note"] = license_note
    return row
