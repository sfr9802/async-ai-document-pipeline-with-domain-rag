from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str):
    path = ROOT / "ai-worker" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


a0_snapshot = load_script("rag_xlsx_current_diagnostic_snapshot")
a1_review = load_script("rag_xlsx_v3_failure_case_review")
a4_contract = load_script("rag_xlsx_formula_date_contract_phase_review")
a5_decision = load_script("rag_xlsx_candidate_v2_decision")
a6_compare = load_script("rag_xlsx_after_cleanup_compare")
hard_case_probe = load_script("rag_xlsx_remaining_hard_case_probe")


def test_a0_blocks_canary_artifact_hash_drift(tmp_path: Path):
    fixture = make_a0_fixture(tmp_path)

    completed = a0_snapshot.build_snapshot_report(
        args=fixture.args,
        positive_rows=fixture.gold_rows,
        diagnostic_report=fixture.diagnostic_report,
        performance_summary=fixture.performance_summary,
        failure_breakdown=fixture.failure_breakdown,
        hidden_report=fixture.hidden_report,
    )
    assert completed["status"] == "COMPLETED"

    (fixture.canary_dir / "faiss.index").write_text("changed", encoding="utf-8")
    blocked = a0_snapshot.build_snapshot_report(
        args=fixture.args,
        positive_rows=fixture.gold_rows,
        diagnostic_report=fixture.diagnostic_report,
        performance_summary=fixture.performance_summary,
        failure_breakdown=fixture.failure_breakdown,
        hidden_report=fixture.hidden_report,
    )

    assert blocked["status"] == "BLOCKED"
    assert "baseline_hash_unchanged" in blocked["blockers"]
    assert "rag_data_canary_hash_unchanged" in blocked["blockers"]


def test_a1_requires_all_degraded_rows_to_be_reviewed():
    target_ids = list(a1_review.DEFAULT_TARGET_QUERY_IDS)
    extra_id = "gq_extra_regression"
    gold_rows = [{"query_id": query_id, "query": query_id} for query_id in [*target_ids, extra_id]]
    diagnostic_report = {
        "query_results": [{"query_id": query_id, "query": query_id} for query_id in [*target_ids, extra_id]]
    }
    failure_breakdown = {
        "failed_or_degraded_rows": [
            {
                "query_id": query_id,
                "category": "QUERY_NATURALIZATION_DRIFT",
                "rationale": "fixture",
            }
            for query_id in [*target_ids, extra_id]
        ]
    }
    args = SimpleNamespace(
        positive_gold="gold.csv",
        diagnostic_report="diag.json",
        failure_breakdown="breakdown.json",
        target_query_ids=",".join(target_ids),
    )

    payload = a1_review.build_review(
        args=args,
        gold_rows=gold_rows,
        diagnostic_report=diagnostic_report,
        failure_breakdown=failure_breakdown,
    )

    assert payload["status"] == "NEEDS_REVIEW"
    assert payload["unreviewed_degraded_query_ids"] == [extra_id]
    assert "unreviewed_degraded_query_ids" in payload["blockers"]


def test_a1_cli_returns_nonzero_when_review_is_incomplete(tmp_path: Path):
    target_ids = list(a1_review.DEFAULT_TARGET_QUERY_IDS)
    extra_id = "gq_extra_regression"
    gold_path = tmp_path / "gold.csv"
    diagnostic_path = tmp_path / "diagnostic.json"
    failure_path = tmp_path / "failure.json"
    output_path = tmp_path / "review.json"
    write_csv(gold_path, [{"query_id": query_id, "query": query_id} for query_id in [*target_ids, extra_id]])
    write_json(
        diagnostic_path,
        {"query_results": [{"query_id": query_id, "query": query_id} for query_id in [*target_ids, extra_id]]},
    )
    write_json(
        failure_path,
        {
            "failed_or_degraded_rows": [
                {"query_id": query_id, "category": "QUERY_NATURALIZATION_DRIFT"}
                for query_id in [*target_ids, extra_id]
            ]
        },
    )

    code = a1_review.main(
        [
            "--positive-gold",
            str(gold_path),
            "--diagnostic-report",
            str(diagnostic_path),
            "--failure-breakdown",
            str(failure_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 1
    assert read_json(output_path)["status"] == "NEEDS_REVIEW"


def test_a4_requires_db_surface_evidence_and_redacts_uri_credentials():
    target = {
        "query_id": a4_contract.TARGET_QUERY_ID,
        "expected_document_version_id": "docv_target",
        "expected_file_name": "sample.xlsx",
        "expected_sheet_name": "Sheet1",
        "expected_cell_range": "A2:J51",
    }
    args = SimpleNamespace(
        a1_review="a1.json",
        prior_contract_review="prior.json",
        surface_output="surface.json",
        reviewed_gold="reviewed.csv",
        query_id=a4_contract.TARGET_QUERY_ID,
        db_dsn="postgresql://user:secret@localhost/db password=secret2",
    )

    surface = a4_contract.build_surface_report(
        args=args,
        target=target,
        prior_target={},
        prior_contract={},
        db_evidence={"status": "DB_QUERY_FAILED", "rows": []},
    )
    contract = a4_contract.build_contract_report(
        args=args,
        target=target,
        prior_target={},
        prior_contract={},
        surface=surface,
    )

    assert surface["status"] == "NEEDS_REVIEW"
    assert contract["status"] == "NEEDS_REVIEW"
    assert "db_surface_evidence_completed" in surface["blockers"]
    redacted = a4_contract.redact_dsn(args.db_dsn)
    assert "secret" not in redacted
    assert "password=<redacted>" in redacted


def test_a4_cli_returns_nonzero_when_db_surface_evidence_is_missing(tmp_path: Path, monkeypatch):
    a1_path = tmp_path / "a1.json"
    prior_path = tmp_path / "prior.json"
    reviewed_path = tmp_path / "reviewed.csv"
    contract_path = tmp_path / "contract.json"
    surface_path = tmp_path / "surface.json"
    write_json(
        a1_path,
        {
            "rows": [
                {
                    "query_id": a4_contract.TARGET_QUERY_ID,
                    "expected_document_version_id": "docv_target",
                    "expected_file_name": "sample.xlsx",
                    "expected_sheet_name": "Sheet1",
                    "expected_cell_range": "A2:J51",
                }
            ]
        },
    )
    write_json(prior_path, {"rows": []})
    write_csv(reviewed_path, [{"query_id": a4_contract.TARGET_QUERY_ID, "query": "old"}])
    monkeypatch.setattr(
        a4_contract,
        "load_db_surface_evidence",
        lambda *, args, target: {"status": "DB_QUERY_FAILED", "rows": []},
    )

    code = a4_contract.main(
        [
            "--a1-review",
            str(a1_path),
            "--prior-contract-review",
            str(prior_path),
            "--contract-output",
            str(contract_path),
            "--surface-output",
            str(surface_path),
            "--reviewed-gold",
            str(reviewed_path),
        ]
    )

    assert code == 1
    assert read_json(contract_path)["status"] == "NEEDS_REVIEW"


def test_a5_does_not_skip_when_candidate_v2_is_required():
    query_surface = {
        "status": "COMPLETED",
        "reviewed_query_count": 1,
        "query_quality_audit": {"pass": True},
    }
    range_policy = {"status": "COMPLETED", "policy_decision": "KEEP"}
    formula_date = {
        "status": "COMPLETED",
        "next_action": "QUERY_REWRITE",
        "candidate_v2_required_now": True,
    }
    args = SimpleNamespace(
        query_surface_plan="a2.json",
        range_policy_review="a3.json",
        formula_date_review="a4.json",
    )

    payload = a5_decision.build_decision(
        args=args,
        query_surface=query_surface,
        range_policy=range_policy,
        formula_date=formula_date,
    )

    assert payload["status"] == "NEEDS_REVIEW"
    assert payload["decision"] == "CREATE_V2_REQUIRED"
    assert payload["completion_criteria"]["candidate_v2_required_now"] is True


def test_a5_cli_returns_nonzero_when_candidate_v2_is_required(tmp_path: Path):
    query_surface_path = tmp_path / "a2.json"
    range_policy_path = tmp_path / "a3.json"
    formula_path = tmp_path / "a4.json"
    output_path = tmp_path / "decision.json"
    write_json(query_surface_path, {"status": "COMPLETED", "reviewed_query_count": 1, "query_quality_audit": {"pass": True}})
    write_json(range_policy_path, {"status": "COMPLETED", "policy_decision": "KEEP"})
    write_json(
        formula_path,
        {"status": "COMPLETED", "next_action": "QUERY_REWRITE", "candidate_v2_required_now": True},
    )

    code = a5_decision.main(
        [
            "--query-surface-plan",
            str(query_surface_path),
            "--range-policy-review",
            str(range_policy_path),
            "--formula-date-review",
            str(formula_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 1
    assert read_json(output_path)["decision"] == "CREATE_V2_REQUIRED"


def test_a6_blocks_invalid_gold_contract_and_hidden_leakage():
    args = SimpleNamespace(
        before_report="before.json",
        after_report="after.json",
        before_gold="before.csv",
        after_gold="after.csv",
        hidden_report="hidden.json",
        candidate_decision="candidate.json",
    )
    before = diagnostic_report(["q1"])
    after = diagnostic_report(["q1"])
    hidden = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "metrics": {"hidden_content_leakage_count": 1},
    }
    candidate = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "decision": "SKIP",
        "candidate_v1_mutated": False,
    }

    payload = a6_compare.build_compare(
        args=args,
        before=before,
        after=after,
        before_gold_rows=[{"query_id": "q1"}],
        after_gold_rows=[{"query_id": "q2"}],
        hidden=hidden,
        candidate_decision=candidate,
    )

    assert payload["status"] == "NEEDS_REVIEW"
    assert "before_after_gold_query_ids_match" in payload["blockers"]
    assert "hidden_content_leakage_count_is_0" in payload["blockers"]


def test_a6_blocks_missing_metrics_and_duplicate_report_query_ids():
    args = SimpleNamespace(
        before_report="before.json",
        after_report="after.json",
        before_gold="before.csv",
        after_gold="after.csv",
        hidden_report="hidden.json",
        candidate_decision="candidate.json",
    )
    before = diagnostic_report(["q1", "q2"])
    after = diagnostic_report(["q1", "q2"])
    before["metrics"].pop("xlsx_citation_location_accuracy")
    after["query_results"].append(dict(after["query_results"][0]))
    hidden = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "metrics": {"hidden_content_leakage_count": 0},
    }
    candidate = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "decision": "SKIP",
        "candidate_v1_mutated": False,
    }

    payload = a6_compare.build_compare(
        args=args,
        before=before,
        after=after,
        before_gold_rows=[{"query_id": "q1"}, {"query_id": "q2"}],
        after_gold_rows=[{"query_id": "q1"}, {"query_id": "q2"}],
        hidden=hidden,
        candidate_decision=candidate,
    )

    assert payload["status"] == "NEEDS_REVIEW"
    assert "metrics_are_finite" in payload["blockers"]
    assert "after_report_has_no_duplicate_query_ids" in payload["blockers"]
    assert "after_report_row_count_matches_gold" in payload["blockers"]


def test_a6_cli_returns_nonzero_when_compare_needs_review(tmp_path: Path):
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_gold_path = tmp_path / "before.csv"
    after_gold_path = tmp_path / "after.csv"
    hidden_path = tmp_path / "hidden.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "compare.json"
    write_json(before_path, diagnostic_report(["q1"]))
    write_json(after_path, diagnostic_report(["q1"]))
    write_csv(before_gold_path, [{"query_id": "q1"}])
    write_csv(after_gold_path, [{"query_id": "q2"}])
    write_json(
        hidden_path,
        {
            "status": "COMPLETED",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "metrics": {"hidden_content_leakage_count": 1},
        },
    )
    write_json(
        candidate_path,
        {
            "status": "COMPLETED",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "decision": "SKIP",
            "candidate_v1_mutated": False,
        },
    )

    code = a6_compare.main(
        [
            "--before-report",
            str(before_path),
            "--after-report",
            str(after_path),
            "--before-gold",
            str(before_gold_path),
            "--after-gold",
            str(after_gold_path),
            "--hidden-report",
            str(hidden_path),
            "--candidate-decision",
            str(candidate_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 1
    assert read_json(output_path)["status"] == "NEEDS_REVIEW"


def test_hard_case_probe_rejects_query_missing_semantic_anchor():
    row = {
        "expected_file_name": "transport.xlsx",
        "expected_sheet_name": "철도",
        "expected_cell_range": "A502:D551",
        "must_contain_terms": "신분당선;승차총승객수",
    }

    audit = hard_case_probe.audit_query_variant("신분당선", row)

    assert audit["pass"] is False
    assert audit["missing_required_terms"] == ["승차총승객수"]
    assert "semantic_anchor_missing" in audit["failures"]


def test_hard_case_probe_rejects_missing_semantic_anchor_metadata():
    row = {
        "expected_file_name": "transport.xlsx",
        "expected_sheet_name": "철도",
        "expected_cell_range": "A502:D551",
    }

    audit = hard_case_probe.audit_query_variant("신분당선", row)

    assert audit["pass"] is False
    assert audit["required_terms"] == []
    assert "semantic_anchor_metadata_missing" in audit["failures"]


def test_hard_case_probe_prefers_reviewed_metadata_anchor_override():
    row = {
        "query_id": "gq_auto_041",
        "expected_file_name": "care.xlsx",
        "expected_sheet_name": "일반현황",
        "expected_cell_range": "A952:J1001",
        "must_contain_terms": "인하요양원;주소",
    }

    stale = hard_case_probe.audit_query_variant("인하요양원 주소 정보 찾아줘.", row)
    reviewed = hard_case_probe.audit_query_variant("인하요양원 소재지 정보 찾아줘.", row)

    assert stale["pass"] is False
    assert stale["missing_required_terms"] == ["소재지"]
    assert reviewed["pass"] is True
    assert reviewed["required_terms"] == ["인하요양원", "소재지"]


def make_a0_fixture(tmp_path: Path) -> SimpleNamespace:
    gold_path = tmp_path / "gold.csv"
    diagnostic_path = tmp_path / "diagnostic.json"
    performance_path = tmp_path / "performance.json"
    failure_path = tmp_path / "failure.json"
    hidden_path = tmp_path / "hidden.json"
    candidate_dir = tmp_path / "rag-data-xlsx-candidate-v1"
    canary_dir = tmp_path / "rag-data-canary"
    baseline_path = tmp_path / "baseline.json"

    candidate_dir.mkdir()
    canary_dir.mkdir()
    write_json(candidate_dir / "build.json", {"index_version": a0_snapshot.XLSX_CANDIDATE_INDEX_VERSION})
    (candidate_dir / "faiss.index").write_text("candidate", encoding="utf-8")
    write_json(candidate_dir / "ingest_manifest.json", {"index_version": a0_snapshot.XLSX_CANDIDATE_INDEX_VERSION})
    (canary_dir / "faiss.index").write_text("canary", encoding="utf-8")
    write_json(canary_dir / "build.json", {"index_version": "baseline"})
    write_json(canary_dir / "ingest_manifest.json", {"embedding_model": "test"})

    gold_rows = [{"query_id": f"q{i:02d}", "query": "lookup"} for i in range(35)]
    write_csv(gold_path, gold_rows)
    diagnostic_report = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "metrics": {"Hit@10": 1.0},
    }
    performance_summary = {"status": "COMPLETED", "metrics": {"Hit@10": 1.0}}
    failure_breakdown = {"status": "COMPLETED", "failed_or_degraded_rows": []}
    hidden_report = {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "metrics": {"hidden_content_leakage_count": 0},
    }
    write_json(diagnostic_path, diagnostic_report)
    write_json(performance_path, performance_summary)
    write_json(failure_path, failure_breakdown)
    write_json(hidden_path, hidden_report)
    write_json(baseline_path, {"faiss_artifact_hashes": artifact_hashes(canary_dir)})

    args = SimpleNamespace(
        positive_gold=str(gold_path),
        diagnostic_report=str(diagnostic_path),
        performance_summary=str(performance_path),
        failure_breakdown=str(failure_path),
        hidden_leakage_report=str(hidden_path),
        artifact_dir=str(candidate_dir),
        baseline_descriptor=str(baseline_path),
        rag_data_canary=str(canary_dir),
        candidate_index_version=a0_snapshot.XLSX_CANDIDATE_INDEX_VERSION,
        required_index_version=a0_snapshot.XLSX_CANDIDATE_INDEX_VERSION,
    )
    return SimpleNamespace(
        args=args,
        gold_rows=gold_rows,
        diagnostic_report=diagnostic_report,
        performance_summary=performance_summary,
        failure_breakdown=failure_breakdown,
        hidden_report=hidden_report,
        canary_dir=canary_dir,
    )


def diagnostic_report(query_ids: list[str]) -> dict:
    return {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "validation": {"ok": True},
        "metrics": {key: 1.0 for key in a6_compare.METRIC_KEYS},
        "query_results": [
            {
                "query_id": query_id,
                "query": "query",
                "hit_rank": 1,
                "location_rank": 1,
                "location_match": True,
                "top_k_results": [
                    {
                        "rank": 1,
                        "chunk_type": "row_group",
                        "match_breakdown": {
                            "file_match": True,
                            "document_version_match": True,
                            "xlsx_sheet_match": True,
                            "xlsx_range_exact": True,
                        },
                    }
                ],
            }
            for query_id in query_ids
        ],
    }


def artifact_hashes(path: Path) -> dict[str, str]:
    return {
        file_path.relative_to(path).as_posix(): sha256_file(file_path)
        for file_path in sorted(path.rglob("*"))
        if file_path.is_file()
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
