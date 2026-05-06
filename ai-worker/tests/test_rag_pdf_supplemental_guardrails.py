from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "ai-worker" / "scripts"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


common = load_module("rag_pdf_supplemental_common")
pageindex = load_module("rag_pdf_supplemental_pageindex_diagnostic")


def test_supplemental_output_paths_reject_protected_and_non_supplemental_names():
    protected_path = common.ROOT / "ai-worker/eval/eval_queries/gold_queries_pdf_v0.csv"
    generic_report = common.REPORT_DIR / "rag_pdf_report.json"
    safe_paths = {
        "query_csv": common.EVAL_QUERIES_DIR / "gold_queries_pdf_supplemental_tmp_diagnostic.csv",
        "review_csv": common.REVIEW_DIR / "pdf_supplemental_tmp_review_pack.csv",
        "json_report": common.REPORT_DIR / "rag_pdf_supplemental_tmp_report.json",
    }

    findings = common.supplemental_output_path_findings({
        "protected_query_csv": protected_path,
        "generic_json_report": generic_report,
    })

    assert "protected_query_csv" in findings
    assert any("protected" in reason for reason in findings["protected_query_csv"])
    assert "generic_json_report" in findings
    assert any("supplemental-specific" in reason for reason in findings["generic_json_report"])
    assert common.supplemental_output_path_findings(safe_paths) == {}


def test_protected_source_blockers_fail_closed_on_missing_or_hash_drift(tmp_path: Path, monkeypatch):
    protected_rel = "ai-worker/eval/eval_queries/gold_queries_pdf_v0.csv"
    protected_path = tmp_path / protected_rel
    protected_path.parent.mkdir(parents=True)
    protected_path.write_text("stable\n", encoding="utf-8")
    digest = hashlib.sha256(protected_path.read_bytes()).hexdigest()

    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PROTECTED_SOURCE_SHA256", {protected_rel: digest})

    assert common.protected_source_blockers() == []

    protected_path.write_text("drift\n", encoding="utf-8")
    assert common.protected_source_blockers() == [f"protected source hash drift: {protected_rel}"]

    protected_path.unlink()
    assert common.protected_source_blockers() == [f"protected source missing: {protected_rel}"]


def test_pageindex_manifest_identity_rejects_stale_or_mismatched_manifest(tmp_path: Path):
    input_manifest = {"run_id": "fresh-run"}
    input_manifest_path = tmp_path / "pageindex_supplemental_input_manifest.json"
    input_manifest_sha256 = "expected-sha"

    blockers = pageindex.pageindex_manifest_identity_blockers(
        {
            "run_id": "old-run",
            "input_manifest": "old-input.json",
            "input_manifest_sha256": "old-sha",
            "status": "COMPLETED",
        },
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        input_manifest_sha256=input_manifest_sha256,
        runner_returncode=1,
    )

    assert any("run_id" in blocker for blocker in blockers)
    assert any("input_manifest path" in blocker for blocker in blockers)
    assert any("input_manifest_sha256" in blocker for blocker in blockers)
    assert any("non-zero" in blocker for blocker in blockers)


def test_pageindex_manifest_identity_allows_explicit_fail_closed_manifest(tmp_path: Path):
    input_manifest = {"run_id": "fresh-run"}
    input_manifest_path = tmp_path / "pageindex_supplemental_input_manifest.json"
    input_manifest_sha256 = "expected-sha"

    blockers = pageindex.pageindex_manifest_identity_blockers(
        {
            "run_id": "fresh-run",
            "input_manifest": pageindex.display_path(input_manifest_path),
            "input_manifest_sha256": input_manifest_sha256,
            "status": "FAIL_CLOSED_PAGEINDEX_UNAVAILABLE",
        },
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        input_manifest_sha256=input_manifest_sha256,
        runner_returncode=2,
    )

    assert blockers == []
