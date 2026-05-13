from __future__ import annotations

import importlib.util
import csv
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_xlsx_pre_silver_risk_closure.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_pre_silver_risk_closure_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


closure = load_module()


def good_official_route_kwargs() -> dict:
    return {
        "eval_mode": "official",
        "track": "XLSX",
        "agent_orchestrator_enabled": False,
        "retrieval_backend": "vector",
        "namespace": closure.XLSX_CANDIDATE_NAMESPACE,
        "vector_index_dir": closure.XLSX_CANDIDATE_INDEX_DIR,
        "positive_gold": closure.CURRENT_XLSX_RETRIEVAL_GOLD,
        "candidate_index_version": closure.XLSX_CANDIDATE_NAMESPACE,
        "required_index_version": closure.XLSX_CANDIDATE_NAMESPACE,
        "combined_retrieval_enabled": False,
    }


def good_iteration_record() -> dict:
    return {
        "trace_id": "trace-q1",
        "query_id": "q1",
        "eval_mode": "diagnostic",
        "track": "XLSX",
        "namespace": closure.XLSX_CANDIDATE_NAMESPACE,
        "iteration": 0,
        "action_type": "retrieval",
        "retriever_or_tool_name": "xlsx_vector_candidate_retriever",
        "input_query": "lookup",
        "rewritten_query": "",
        "candidate_ids": ["su1"],
        "selected_context_ids": ["ctx1"],
        "stop_reason": "completed",
        "fallback_reason": "",
        "max_iterations": 2,
    }


def test_official_xlsx_eval_rejects_generic_agent_orchestrator():
    kwargs = good_official_route_kwargs()
    kwargs["agent_orchestrator_enabled"] = True

    with pytest.raises(closure.XlsxPreSilverRiskError, match="official XLSX eval uses the XLSX wrapper"):
        closure.validate_official_xlsx_eval_route(**kwargs)


def test_official_xlsx_route_rejects_same_named_noncanonical_positive_gold(tmp_path: Path):
    fake = tmp_path / closure.CURRENT_XLSX_RETRIEVAL_GOLD.name
    fake.write_text("query_id,query,expected_location_type\nq,lookup,xlsx\n", encoding="utf-8")
    kwargs = good_official_route_kwargs()
    kwargs["positive_gold"] = fake

    with pytest.raises(closure.XlsxPreSilverRiskError, match="canonical current human-review"):
        closure.validate_official_xlsx_eval_route(**kwargs)


def test_official_xlsx_route_rejects_combined_nonvector_wrong_namespace_and_index(tmp_path: Path):
    variants = [
        ("combined_retrieval_enabled", True, "combined retrieval"),
        ("retrieval_backend", "library_search", "vector XLSX candidate retrieval"),
        ("namespace", "rag-ingestion-v2-text", "XLSX namespace"),
        ("candidate_index_version", "rag-ingestion-v2-text", "candidate_index_version"),
        ("required_index_version", "rag-ingestion-v2-text", "required_index_version"),
        ("vector_index_dir", tmp_path / "rag-data-xlsx-candidate-v1", "candidate index directory"),
    ]
    for key, value, message in variants:
        kwargs = good_official_route_kwargs()
        kwargs[key] = value
        with pytest.raises(closure.XlsxPreSilverRiskError, match=message):
            closure.validate_official_xlsx_eval_route(**kwargs)


def test_diagnostic_agentic_xlsx_requires_explicit_allow_flag():
    with pytest.raises(closure.XlsxPreSilverRiskError, match="explicit allow flag"):
        closure.validate_diagnostic_agentic_xlsx_config(
            eval_mode="diagnostic",
            track="XLSX",
            namespace=closure.XLSX_CANDIDATE_NAMESPACE,
            agent_orchestrator_enabled=True,
            diagnostic_agentic_allow=False,
            retriever_names=["xlsx_vector_candidate_retriever"],
            max_iterations=2,
        )


def test_agentic_xlsx_loop_preserves_track_and_namespace():
    closure.validate_agentic_iteration_record(good_iteration_record())
    bad_track = good_iteration_record()
    bad_track["track"] = "PDF"

    with pytest.raises(closure.XlsxPreSilverRiskError, match="track=XLSX"):
        closure.validate_agentic_iteration_record(bad_track)

    bad = good_iteration_record()
    bad["namespace"] = "rag-ingestion-v2-text"

    with pytest.raises(closure.XlsxPreSilverRiskError, match="XLSX namespace"):
        closure.validate_agentic_iteration_record(bad)


def test_agentic_xlsx_loop_disallows_global_fallback():
    with pytest.raises(closure.XlsxPreSilverRiskError, match="global fallback"):
        closure.validate_diagnostic_agentic_xlsx_config(
            eval_mode="diagnostic",
            track="XLSX",
            namespace=closure.XLSX_CANDIDATE_NAMESPACE,
            agent_orchestrator_enabled=True,
            diagnostic_agentic_allow=True,
            retriever_names=["xlsx_vector_candidate_retriever"],
            global_fallback_enabled=True,
            max_iterations=2,
        )


def test_agentic_xlsx_loop_disallows_text_pdf_retrievers():
    with pytest.raises(closure.XlsxPreSilverRiskError, match="global/TEXT/PDF"):
        closure.validate_diagnostic_agentic_xlsx_config(
            eval_mode="diagnostic",
            track="XLSX",
            namespace=closure.XLSX_CANDIDATE_NAMESPACE,
            agent_orchestrator_enabled=True,
            diagnostic_agentic_allow=True,
            retriever_names=["xlsx_vector_candidate_retriever", "pdf_vector_retriever"],
            max_iterations=2,
        )


def test_agentic_xlsx_loop_disallows_external_search():
    with pytest.raises(closure.XlsxPreSilverRiskError, match="external search"):
        closure.validate_diagnostic_agentic_xlsx_config(
            eval_mode="diagnostic",
            track="XLSX",
            namespace=closure.XLSX_CANDIDATE_NAMESPACE,
            agent_orchestrator_enabled=True,
            diagnostic_agentic_allow=True,
            retriever_names=["xlsx_vector_candidate_retriever"],
            external_search_enabled=True,
            max_iterations=2,
        )


def test_agentic_xlsx_loop_disallows_web_search_action():
    bad = good_iteration_record()
    bad["action_type"] = "web_search"

    with pytest.raises(closure.XlsxPreSilverRiskError, match="external search"):
        closure.validate_agentic_iteration_record(bad)


def test_agentic_xlsx_loop_bounds_max_iterations():
    for value in (0, 6):
        with pytest.raises(closure.XlsxPreSilverRiskError, match="bounded max_iterations"):
            closure.validate_diagnostic_agentic_xlsx_config(
                eval_mode="diagnostic",
                track="XLSX",
                namespace=closure.XLSX_CANDIDATE_NAMESPACE,
                agent_orchestrator_enabled=True,
                diagnostic_agentic_allow=True,
                retriever_names=["xlsx_vector_candidate_retriever"],
                max_iterations=value,
            )


def test_agentic_xlsx_loop_records_stop_reason():
    bad = good_iteration_record()
    bad["stop_reason"] = ""

    with pytest.raises(closure.XlsxPreSilverRiskError, match="stop_reason"):
        closure.validate_agentic_iteration_record(bad)


def test_xlsx_eval_resolves_current_human_review_artifacts():
    manifest = closure.resolve_current_xlsx_human_review_artifacts(require_source_snapshot=True)

    assert manifest["normalized_row_count"] == 50
    assert manifest["official_positive_retrieval_row_count"] == 23
    assert manifest["artifacts"]["official_positive_retrieval"]["hash_matches_registry"] is True
    assert manifest["source_snapshot"]["hash_matches_registry"] is True


def test_current_xlsx_human_review_denominator_is_23():
    manifest = closure.resolve_current_xlsx_human_review_artifacts(require_source_snapshot=True)

    assert manifest["official_positive_row_count"] == 23
    assert manifest["official_positive_retrieval_row_count"] == 23


def test_xlsx_answer_generation_denominator_remains_zero():
    manifest = closure.resolve_current_xlsx_human_review_artifacts(require_source_snapshot=True)

    assert manifest["official_xlsx_answer_generation_denominator"] == 0


def test_legacy_xlsx_v3_35_rows_are_superseded_not_current():
    registry = json.loads(closure.OFFICIAL_REGISTRY.read_text(encoding="utf-8"))
    legacy = registry["official_diagnostic_denominators"]["track_a_xlsx_reviewed_positive"]

    assert legacy["row_count"] == 35
    assert legacy["current_default"] is False
    assert legacy["superseded_by"] == "track_a_xlsx_human_review_normalized_v0"
    assert registry["current_defaults"]["track_a_xlsx"]["denominator_key"] == "track_a_xlsx_human_review_normalized_v0"


def test_xlsx_special_rows_remain_non_official():
    rows = {
        row["query_id"]: row
        for row in closure.read_csv_rows(
            ROOT / "ai" / "eval" / "eval_queries" / "gold_queries_xlsx_human_review_normalized_v0.csv"
        )
    }

    for query_id in closure.SPECIAL_NON_OFFICIAL_QUERY_IDS:
        assert rows[query_id]["include_in_official_positive_denominator"] == "FALSE"
        assert rows[query_id]["derived_denominator_policy"] != "OFFICIAL_POSITIVE"


def test_no_silver_rows_in_official_denominator():
    rows = closure.read_csv_rows(
        ROOT / "ai" / "eval" / "eval_queries" / "gold_queries_xlsx_human_review_official_positive_v0.csv"
    )

    assert all("silver" not in row["query_id"].lower() for row in rows)


def test_xlsx_eval_does_not_fallback_to_stale_artifact():
    kwargs = good_official_route_kwargs()
    kwargs["positive_gold"] = "eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv"

    with pytest.raises(closure.XlsxPreSilverRiskError, match="current human-review"):
        closure.validate_official_xlsx_eval_route(**kwargs)


def test_xlsx_retrieval_diagnostic_uses_registry_resolved_positive_gold(tmp_path: Path):
    fake = tmp_path / closure.CURRENT_XLSX_RETRIEVAL_GOLD.name
    fake.write_text("query_id,query,expected_location_type\nq,lookup,xlsx\n", encoding="utf-8")
    kwargs = good_official_route_kwargs()
    kwargs["positive_gold"] = fake

    with pytest.raises(closure.XlsxPreSilverRiskError, match="canonical current human-review"):
        closure.validate_official_xlsx_eval_route(**kwargs)


def test_silver_generation_requires_strict_preflight_status():
    blocked = {
        "status": closure.BLOCKED_STATUS,
        "official_xlsx_retrieval_evidence_denominator": 23,
        "official_xlsx_answer_generation_denominator": 0,
    }
    approved = {
        "status": closure.STRICT_APPROVAL_STATUS,
        "official_xlsx_retrieval_evidence_denominator": 23,
        "official_xlsx_answer_generation_denominator": 0,
        "diagnostic_llm_metric_included_in_official": False,
        "generic_agent_orchestrator_allowed_for_official_xlsx": False,
    }

    assert closure.silver_generation_requires_strict_preflight_status(blocked) is False
    assert closure.silver_generation_requires_strict_preflight_status(approved) is True


def test_pre_silver_report_counts_match_probe_artifacts():
    report = json.loads(
        (ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "xlsx_pre_silver_risk_closure_20260507.json")
        .read_text(encoding="utf-8")
    )
    live_dir = (
        ROOT
        / "ai"
        / "eval"
        / "artifacts"
        / "eval_runs"
        / "xlsx_pre_silver_llm_answer_probe_20260507Tpre_silver_strict_live"
    )
    repeat_dir = live_dir.with_name("xlsx_pre_silver_llm_answer_probe_20260507Tpre_silver_strict_live_repeat")
    live_probe = json.loads((live_dir / "llm_answer_probe_report.json").read_text(encoding="utf-8"))
    repeat_probe = json.loads((repeat_dir / "llm_answer_probe_report.json").read_text(encoding="utf-8"))
    rows = read_csv(live_dir / "llm_answer_probe_report.csv")
    repeat_rows = read_csv(repeat_dir / "llm_answer_probe_report.csv")

    assert report["llm_diagnostic_smoke"]["status"] == live_probe["status"]
    assert report["llm_diagnostic_smoke"]["repeat_status"] == repeat_probe["status"]
    assert report["llm_diagnostic_smoke"]["row_count"] == len(rows)
    assert report["llm_diagnostic_smoke"]["llm_invalid_json_count"] == live_probe["llm_invalid_json_count"]
    assert report["llm_diagnostic_smoke"]["llm_keyword_only_rejected_count"] == sum(
        row["content_shape_status"] == "KEYWORD_ONLY_REJECTED" for row in rows
    )
    assert report["llm_diagnostic_smoke"]["official_xlsx_answer_eval_denominator"] == 0
    assert all(row["official_metric_included"].upper() == "FALSE" for row in rows)
    assert all(row["answer_generation_denominator_included"].upper() == "FALSE" for row in rows)
    assert status_signature(rows) == status_signature(repeat_rows)


def test_pre_silver_report_verification_blocks_are_consistent():
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "xlsx_pre_silver_risk_closure_20260507.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    serialized = json.dumps(report, ensure_ascii=False)

    assert "invalid_json=2" not in serialized
    assert "1 skipped" not in serialized
    assert "2 warnings" not in serialized
    focused_pytest = report["verification_results"]["focused_pytest"]
    assert any("test_rag_xlsx_pre_silver_risk_closure.py" in command for command in report["commands_run"])
    assert report["tests_and_commands"] == [
        {"command": command, "result": result}
        for command, result in zip(
            report["commands_run"],
            [
                "passed",
                focused_pytest,
                "passed; normalized=50; official_positive=23; answer_denominator=0",
                "passed; Hit@10=1.0; MRR@10=0.942; XLSX citation/location=1.0",
                "passed; repeat metrics and candidate order stable",
                "passed as diagnostic; PASS_WITH_WARNINGS; invalid_json=3; keyword_only_rejected=5; official answer denominator=0",
                "passed as diagnostic; repeat status signature stable",
            ],
        )
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def status_signature(rows: list[dict[str, str]]) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (
            row["query_id"],
            row["raw_output_status"],
            row["parser_status"],
            row["content_shape_status"],
            row["citation_validation_status"],
            row["llm_smoke_status"],
        )
        for row in rows
    ]


def test_official_xlsx_resolver_validates_registry_hashes(tmp_path: Path):
    registry = json.loads(closure.OFFICIAL_REGISTRY.read_text(encoding="utf-8"))
    current = registry["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"]
    current["official_positive_retrieval_subset_sha256"] = "0" * 64
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(closure.XlsxPreSilverRiskError, match="hash mismatch"):
        closure.resolve_current_xlsx_human_review_artifacts(registry_path=registry_path)


def test_official_xlsx_resolver_requires_registry_hashes(tmp_path: Path):
    registry = json.loads(closure.OFFICIAL_REGISTRY.read_text(encoding="utf-8"))
    current = registry["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"]
    current.pop("official_positive_retrieval_subset_sha256")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(closure.XlsxPreSilverRiskError, match="registry hash missing"):
        closure.resolve_current_xlsx_human_review_artifacts(registry_path=registry_path)


def test_official_xlsx_resolver_rejects_absolute_or_noncanonical_artifact_paths(tmp_path: Path):
    registry = json.loads(closure.OFFICIAL_REGISTRY.read_text(encoding="utf-8"))
    current = registry["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"]
    official_src = ROOT / current["official_positive_retrieval_subset_path"]
    official_dst = tmp_path / official_src.name
    official_dst.write_text(official_src.read_text(encoding="utf-8"), encoding="utf-8")
    current["official_positive_retrieval_subset_path"] = str(official_dst)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(closure.XlsxPreSilverRiskError, match="canonical"):
        closure.resolve_current_xlsx_human_review_artifacts(registry_path=registry_path)
