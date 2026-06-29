from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
ROLLBACK_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
STATUS = "V6_9_ANSWER_QUALITY_GATE_PACKET_NONPROD_READY"
LATEST_CURRENT_RUN_KEY = RUN_KEY
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "agentic_answer_metric_computed",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "production_cache_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
}


@pytest.fixture(scope="module")
def v69_module():
    from ai.eval import rag_v69_answer_quality_gate_packet_nonprod as v69

    return v69


@pytest.fixture()
def report(v69_module) -> dict[str, object]:
    built = v69_module.build_report(root=ROOT, generated_at="2026-06-07T06:00:00Z")
    v69_module.check_report(built)
    return built


def test_v69_schema_current_and_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == LATEST_CURRENT_RUN_KEY
    assert registry.resolve_run(ROLLBACK_KEY, root=ROOT).logical_key == ROLLBACK_KEY
    assert runner.DEFAULT_RUN_KEY == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["run_id"] == RUN_KEY
    assert report["schema_version"] == "v6_9_answer_quality_gate_packet_nonprod_report_v1"
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v69_answer_quality_gate_is_review_packet_not_metric(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["answer_quality_metric_computed"] is False
    assert report["agentic_answer_metric_computed"] is False
    assert report["human_owned_decisions_filled"] is False
    packet = report["answer_quality_gate_packet"]
    assert packet["packet_location"] == "primary_report_json_only"
    assert packet["review_fields_left_blank"] is True
    assert packet["expected_answer_text_included"] is False
    assert packet["supporting_evidence_text_included"] is False
    assert packet["raw_generated_answer_text_included"] is False
    assert packet["row_count"] == 29


def test_v69_no_raw_prompt_response_payloads(report: dict[str, object]) -> None:
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    for row in report["answer_quality_gate_packet"]["rows"]:
        assert row["human_pass_fail"] == ""
        assert row["human_relevance"] == ""
        assert row["human_answerability"] == ""
        assert row["official_denominator_decision"] == ""
        assert row["promotion_decision"] == ""
        assert row["generated_answer_preview_or_hash"]["redacted"] is True
        assert row["generated_answer_preview_or_hash"]["sha256"]
        assert "generated_final_answer_text" not in row


def test_v69_gate_rows_join_response_tool_agentic_and_retrieval_gate(report: dict[str, object]) -> None:
    rows = report["answer_quality_gate_packet"]["rows"]
    summary = report["answer_quality_gate_summary"]

    assert len(rows) == 29
    assert summary["packet_rows"] == 29
    assert summary["rows_by_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert summary["human_owned_blank_rows"] == 29
    assert summary["answer_quality_metric_computed"] is False
    assert report["source_v6_5_1_response_check"]["actual_response_rows_attempted"] == 29
    assert report["source_v6_6_tool_check"]["tool_operation_rows"] == 29
    assert report["source_v6_7_agentic_check"]["agentic_loop_rows"] == 29
    assert report["source_v6_8_retrieval_gate_check"]["retrieval_quality_metric_computed"] is False
    assert report["source_v6_8_retrieval_gate_check"]["computed_only_denominator"] == 0

    for row in rows:
        assert row["gold_row_hash"]
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert row["query_hash"]
        assert isinstance(row["citation_hashes"], list)
        assert row["route_status"]
        assert row["tool_status"]
        assert row["agentic_verification_state"] in {"passed", "failed", "skipped_no_answer", "not_applicable"}
        assert row["expected_answer_hash"]
        assert row["supporting_evidence_hash"]


def test_v69_boundaries_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    policy = report["answer_quality_gate_policy"]
    assert policy["human_review_required_before_metric"] is True
    assert policy["codex_filled_human_review_fields"] is False
    assert policy["expected_supporting_text_excluded"] is True
    assert policy["promotion_decision_left_blank"] is True
    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []


def test_v69_single_primary_report_status_handoff_and_hash_contract(
    tmp_path: Path,
    v69_module,
    report: dict[str, object],
) -> None:
    written, hashes = v69_module.write_report_bundle(tmp_path, report)
    v69_module.check_report(written, root=tmp_path)
    v69_module.update_docs(tmp_path, written)
    v69_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v69_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()
    status_rows = [
        json.loads(line)
        for line in (tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["answer_quality_metric_computed"] is False
    assert status_rows[-1]["human_owned_decisions_filled"] is False
    assert status_rows[-1]["official_metric"] is False

    assert not (tmp_path / "docs").exists()
    handoff = json.loads(
        (tmp_path / "reports/rag_eval/rag-ingestion/worker-handoff" / f"{RUN_KEY}.json").read_text(encoding="utf-8")
    )
    assert handoff["code_writes_local_docs"] is False
    assert handoff["worker_authored_rolling_notes_expected"] is True
    assert handoff["logical_run_key"] == RUN_KEY
    assert RUN_KEY in handoff["fragments"]["progress"]
    assert "human-owned" in handoff["fragments"]["progress"]
    assert "no official/product/promotion/live-readiness claim" in handoff["fragments"]["triage"].lower()


def test_rag_eval_write_v69_emits_worker_handoff_without_docs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import ai.scripts.rag_eval as runner

    calls: list[str] = []
    report = {
        "status": STATUS,
        "current_resolves_to": RUN_KEY,
        "artifact_paths": {"report_json": f"reports/rag_eval/rag-ingestion/runs/{RUN_KEY}/report.json"},
    }

    class FakeV69:
        @staticmethod
        def build_report(*, root: Path) -> dict[str, object]:
            calls.append(f"build:{root}")
            return dict(report)

        @staticmethod
        def check_report(checked: dict[str, object], *, root: Path) -> None:
            calls.append(f"check:{checked['status']}:{root}")

        @staticmethod
        def write_report_bundle(root: Path, written: dict[str, object]) -> tuple[dict[str, object], dict[str, str]]:
            calls.append(f"write:{root}")
            return written, {"report_json_sha256": "fake-report-sha256"}

        @staticmethod
        def update_docs(root: Path, written: dict[str, object]) -> None:
            calls.append(f"handoff:{root}")
            handoff_root = root / "reports/rag_eval/rag-ingestion/worker-handoff"
            handoff_root.mkdir(parents=True, exist_ok=True)
            (handoff_root / f"{RUN_KEY}.json").write_text(
                json.dumps(
                    {
                        "logical_run_key": RUN_KEY,
                        "code_writes_local_docs": False,
                        "worker_authored_rolling_notes_expected": True,
                    }
                ),
                encoding="utf-8",
            )

        @staticmethod
        def append_status(
            root: Path,
            written: dict[str, object],
            *,
            artifact_hashes: dict[str, str],
        ) -> None:
            calls.append(f"status:{artifact_hashes['report_json_sha256']}:{root}")

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "v69", FakeV69)

    assert runner.main([RUN_KEY, "--write"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["run_key"] == RUN_KEY

    assert not (tmp_path / "docs").exists()
    handoff_path = tmp_path / "reports/rag_eval/rag-ingestion/worker-handoff" / f"{RUN_KEY}.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["code_writes_local_docs"] is False
    assert handoff["worker_authored_rolling_notes_expected"] is True
    assert handoff["logical_run_key"] == RUN_KEY
    assert calls == [
        f"build:{tmp_path}",
        f"check:{STATUS}:{tmp_path}",
        f"write:{tmp_path}",
        f"check:{STATUS}:{tmp_path}",
        f"handoff:{tmp_path}",
        f"status:fake-report-sha256:{tmp_path}",
    ]


def test_protected_namespace_git_status_is_clean_for_v69() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", *PROTECTED_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    ("patch", "message"),
    (
        ({"current_resolves_to": ROLLBACK_KEY}, "current"),
        ({"answer_quality_metric_computed": True}, "answer quality"),
        ({"agentic_answer_metric_computed": True}, "agentic answer"),
        ({"human_owned_decisions_filled": True}, "human-owned"),
        ({"answer_quality_gate_packet": {"review_fields_left_blank": False}}, "review fields"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v69_module,
    patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(poisoned.get(key), dict):
            poisoned[key] = dict(poisoned[key], **value)
        else:
            poisoned[key] = value

    with pytest.raises(ValueError, match=message):
        v69_module.check_report(poisoned)
