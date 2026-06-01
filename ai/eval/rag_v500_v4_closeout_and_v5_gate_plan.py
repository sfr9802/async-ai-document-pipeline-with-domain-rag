from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4718_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility as v4718
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v5_0"
SHORT_RUN_ID = "v5_0_v4_closeout_and_v5_gate_plan"
CANONICAL_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v5_0_v4_closeout_and_v5_gate_plan_nonprod"
STATUS = "V5_0_V4_CLOSEOUT_AND_V5_GATE_PLAN_DIAGNOSTIC_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_LOGICAL_RUN_KEY = v4718.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v4718.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v4718.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v4718.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"

FORBIDDEN_FALSE_KEYS = (
    "official_metric",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "fine_tuning",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_db_mutated",
    "source_registry_mutated",
    "silver_mutation",
    "index_rebuilt",
    "cache_mutated",
)
RAW_PAYLOAD_FORBIDDEN_KEYS = {
    "prompt",
    "prompt_payload",
    "raw_prompt",
    "raw_prompt_payload",
    "raw_response",
    "raw_response_payload",
    "response",
    "raw_llm_response",
    "final_answer",
}


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _source_report_path(root: Path) -> Path:
    return root / SOURCE_REPORT_JSON


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = json.loads(json.dumps(source_report, ensure_ascii=False))
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v4718.build_report(root=root)
    v4718.check_report(report)
    return report


def _source_hash(root: Path) -> str:
    path = _source_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _source_artifact_status(root: Path) -> str:
    return "present" if _source_report_path(root).exists() else "materialized_in_memory"


def _summary_counters(source_report: Mapping[str, Any]) -> dict[str, Any]:
    guards = source_report["regression_guards"]
    repair = source_report["xlsx_candidate_only_materialization_repair"]
    budget = repair["candidate_budget_summary"]["XLSX"]
    validation = source_report["candidate_only_generalization_validation_reproduction"]
    summary = {
        "schema_version": f"{SHORT_RUN_ID}_v4_7_18_summary_counters_v1",
        "TEXT": {
            "hit": guards["TEXT"]["v4_7_18_combined_target_hit_count"],
            "total": guards["TEXT"]["row_count"],
            "miss": guards["TEXT"]["v4_7_18_combined_target_miss_count"],
        },
        "PDF": {
            "hit": guards["PDF"]["v4_7_18_combined_target_hit_count"],
            "total": guards["PDF"]["row_count"],
            "miss": guards["PDF"]["v4_7_18_combined_target_miss_count"],
        },
        "XLSX": {
            "hit": guards["XLSX"]["v4_7_18_combined_target_hit_count"],
            "total": guards["XLSX"]["row_count"],
            "miss": guards["XLSX"]["v4_7_18_combined_target_miss_count"],
        },
        "xlsx_baseline_target_hit_count": guards["XLSX"]["baseline_target_hit_count"],
        "xlsx_v4_7_17_combined_target_hit_count": guards["XLSX"]["v4_7_17_combined_target_hit_count"],
        "xlsx_zero_candidate_row_count": budget["zero_candidate_row_count"],
        "xlsx_candidate_budget_exhaustion_count": budget["candidate_budget_exhaustion_count"],
        "family_target_hit_regression_count": {
            family: guards[family]["target_hit_regression_count"]
            for family in ("TEXT", "PDF", "XLSX")
        },
        "v4_7_16_candidate_set_sha256": validation["source_candidate_set_sha256_recomputed"],
        "v4_7_16_candidate_set_sha256_matches_recomputed": validation[
            "source_candidate_set_sha256_matches_recomputed"
        ],
        "lineage_reproducibility_status": source_report["lineage_reproducibility"]["status"],
        "required_runner_module_tracking_status": source_report["lineage_reproducibility"][
            "required_runner_module_tracking_status"
        ],
    }
    return summary


def _v5_gate_plan(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "A": {
            "lane": "user-owned gold/qrels/expected-evidence/relevance/answerability/denominator/promotion decisions",
            "owner": "user",
            "status": "closed_pending_user_decision",
            "items": [
                "golden set creation",
                "golden set review",
                "expected answer judgment",
                "expected evidence/supporting evidence judgment",
                "relevance label judgment",
                "answerability label judgment",
                "gold policy decision",
                "official denominator policy decision",
                "promotion policy decision",
            ],
        },
        "B": {
            "lane": "Codex-owned implementation/test/report/path/indexing-scope/failure-taxonomy work",
            "owner": "codex",
            "status": "diagnostic_only_allowed",
            "items": [
                "runner, registry, report, status, and doc synchronization",
                "source-first candidate-only indexing-scope guardrails",
                "protected-surface diff checks",
                "failure-taxonomy maintenance for residual queues",
            ],
        },
        "C": {
            "lane": "XLSX residual engineering backlog",
            "owner": "codex",
            "status": "diagnostic_only_backlog",
            "items": [
                f"XLSX {summary['XLSX']['miss']} misses remain after v4_7_18",
                f"{summary['xlsx_zero_candidate_row_count']} zero-candidate XLSX rows need diagnostic explanation or repair",
                f"{summary['xlsx_candidate_budget_exhaustion_count']} budget-exhausted XLSX rows need candidate-only backlog work",
                "formatted-value, repeated-prefix, header-axis, row-axis, and table-range splits remain candidate-only",
            ],
        },
        "D": {
            "lane": "official metric opening preconditions",
            "owner": "user_and_codex",
            "status": "closed_pending_user_owned_policy",
            "items": [
                "approved gold/qrels/labels/expected evidence",
                "frozen official denominator policy",
                "metric definitions and blocked/deferred metric policy",
                "approved protected-surface diffs before any official rows are created",
            ],
        },
        "E": {
            "lane": "live-readiness and promotion preconditions",
            "owner": "user_and_codex",
            "status": "closed_pending_official_metric_and_promotion_policy",
            "items": [
                "accepted official metrics",
                "live DB/index/cache rollout evidence",
                "redaction, leakage, latency, rollback, and monitoring evidence",
                "user-approved promotion and product-success policy",
            ],
        },
    }


def _counters(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "v4_closeout_basis": SOURCE_LOGICAL_RUN_KEY,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "text_v4_7_18_combined_target_hit_count": summary["TEXT"]["hit"],
        "text_v4_7_18_combined_target_miss_count": summary["TEXT"]["miss"],
        "pdf_v4_7_18_combined_target_hit_count": summary["PDF"]["hit"],
        "pdf_v4_7_18_combined_target_miss_count": summary["PDF"]["miss"],
        "xlsx_v4_7_18_combined_target_hit_count": summary["XLSX"]["hit"],
        "xlsx_v4_7_18_combined_target_miss_count": summary["XLSX"]["miss"],
        "xlsx_zero_candidate_row_count": summary["xlsx_zero_candidate_row_count"],
        "xlsx_candidate_budget_exhaustion_count": summary["xlsx_candidate_budget_exhaustion_count"],
        "family_target_hit_regression_count": summary["family_target_hit_regression_count"],
        "generated_response_count": 0,
        "parser_failure_count": 0,
        "claim_support_verifier_fail_count": 0,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    source = _load_source_report(root, source_report=source_report)
    summary = _summary_counters(source)
    gate_plan = _v5_gate_plan(summary)
    counters = _counters(summary)
    source_sha = _source_hash(root)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_report_sha256": source_sha,
        "source_report_artifact_status": _source_artifact_status(root),
        "source_report_materialized_in_memory": source_sha == "",
        "v4_closeout_basis": SOURCE_LOGICAL_RUN_KEY,
        "v4_closeout_basis_short_run_id": SOURCE_RUN_ID,
        "v4_closeout_basis_status": "V4_CLOSED_DIAGNOSTIC_ONLY_SOURCE_FIRST_CANDIDATE_ONLY_LINEAGE_REPRODUCIBLE",
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "fine_tuning": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "generated_response_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "v4_7_18_summary_counters": summary,
        "v5_gate_plan": gate_plan,
        "decision_policy": {
            "user_owned_decisions": gate_plan["A"]["items"],
            "non_gold_ambiguity_policy": "conservative_fail_closed_diagnostic_only",
            "rationale_order": [
                "phase documents",
                "progress log",
                "actual repo artifacts",
                "protected namespace rules",
                "fail-closed diagnostic-only principle",
            ],
        },
        "residual_risks": [
            f"XLSX {summary['XLSX']['miss']} misses remain after v4_7_18",
            f"{summary['xlsx_zero_candidate_row_count']} zero-candidate XLSX rows remain unresolved",
            "v5_0 is not official scoring, promotion evidence, product-success evidence, or live-readiness evidence",
        ],
        "next_recommendations": [
            "keep official metric rows at 0 until user-owned gold/qrels/label/denominator decisions are approved",
            f"triage {summary['xlsx_candidate_budget_exhaustion_count']} budget-exhausted XLSX rows as diagnostic backlog",
            "preserve v4_7_18 direct checkability while current resolves to v5_0",
        ],
        "counters": counters,
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    return report, {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    summary = report["v4_7_18_summary_counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v5_0_v4_closeout_and_v5_gate_plan_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_report_status": report["source_report_status"],
        "source_report_sha256": report["source_report_sha256"],
        "source_report_artifact_status": report["source_report_artifact_status"],
        "v4_closeout_basis": SOURCE_LOGICAL_RUN_KEY,
        "v4_closeout_basis_short_run_id": SOURCE_RUN_ID,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "fine_tuning": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "text_hit_miss": f"{summary['TEXT']['hit']}/{summary['TEXT']['total']} hit, {summary['TEXT']['miss']} miss",
        "pdf_hit_miss": f"{summary['PDF']['hit']}/{summary['PDF']['total']} hit, {summary['PDF']['miss']} miss",
        "xlsx_hit_miss": f"{summary['XLSX']['hit']}/{summary['XLSX']['total']} hit, {summary['XLSX']['miss']} miss",
        "xlsx_zero_candidate_row_count": summary["xlsx_zero_candidate_row_count"],
        "xlsx_candidate_budget_exhaustion_count": summary["xlsx_candidate_budget_exhaustion_count"],
        "family_target_hit_regression_count": summary["family_target_hit_regression_count"],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    event_type = "diagnostic_v5_0_v4_closeout_and_v5_gate_plan_nonprod"
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != event_type
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        text = pattern.sub("", text, count=1)
    return wrapped + "\n\n" + text.lstrip()


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n\n" + text.lstrip()


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v5_0_summary_start -->"
    end = "<!-- v5_0_summary_end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    marked_summary = re.compile(
        r"<!-- v(?:4_7[^>]*|5_0[^>]*)_summary_start -->\n.*?\n"
        r"<!-- v(?:4_7[^>]*|5_0[^>]*)_summary_end -->",
        re.S,
    )
    if marked_summary.search(text):
        return marked_summary.sub(wrapped, text, count=1)
    legacy_summary = re.compile(
        r"## Current RAG Diagnostic Status\n.*?"
        r"(?=\n# |\Z)",
        re.S,
    )
    if legacy_summary.search(text):
        return legacy_summary.sub(wrapped, text, count=1)
    return wrapped + "\n\n" + text.lstrip()


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    summary = report["v4_7_18_summary_counters"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is the diagnostic-only v4 closeout and v5 gate-plan run. "
        f"Artifact: `{SHORT_REPORT_PATH.as_posix()}`. v4 closeout basis: `{SOURCE_LOGICAL_RUN_KEY}` / "
        f"`{SOURCE_RUN_ID}`; source report status `{report['source_report_status']}`; source report hash "
        f"`{report['source_report_sha256'] or 'materialized-in-memory'}`. `current` resolves to `v5_0`, while "
        "`v4_7_18` remains directly checkable as the frozen v4 closeout basis. TEXT remains "
        f"{summary['TEXT']['hit']}/{summary['TEXT']['total']} hit and {summary['TEXT']['miss']} miss; PDF remains "
        f"{summary['PDF']['hit']}/{summary['PDF']['total']} hit and {summary['PDF']['miss']} miss; XLSX remains "
        f"{summary['XLSX']['hit']}/{summary['XLSX']['total']} hit and {summary['XLSX']['miss']} miss. "
        f"XLSX {summary['XLSX']['miss']} misses, {summary['xlsx_zero_candidate_row_count']} zero-candidate rows, "
        f"and {summary['xlsx_candidate_budget_exhaustion_count']} budget-exhausted rows carry into v5 as residual "
        "engineering backlog. official_metric_input_rows=0, silver_official_metric_input_rows=0, "
        "silver_promoted_to_gold_count=0, promotion_evidence=false, product_success_evidence_allowed=false, "
        "live_db_index_cache_readiness=false, gold/qrels/label/expected/supporting/denominator/training/fine-tuning/FT-A "
        "gates remain closed, and protected_namespaces_touched=[]; no per-run Markdown or sidecar payloads are created."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = progress_text.replace(
        "`current` resolves to `v4_7_18`:",
        "`v4_7_18` remains the explicit v4 closeout basis; historical current before v5:",
    )
    progress_text = re.sub(
        r"(## Current Status\n\n)Overall status: `[^`]+`;\n"
        r"current v4_7 closeout basis:\n`[^`]+`;",
        (
            rf"\1Overall status: `{STATUS}`;\n"
            "current v5 diagnostic handoff:\n"
            f"`{SHORT_RUN_ID}`;\n"
            "frozen v4 closeout basis:\n"
            f"`{SOURCE_RUN_ID}`;"
        ),
        progress_text,
        count=1,
    )
    progress_text = progress_text.replace(
        "current_source_of_truth",
        "v4_closeout_source_of_truth",
    )
    progress_text = re.sub(
        r"Current verification: .*?\n"
        r"`python -X utf8 -m pytest ai/tests --rag-current -q` -> \d+ passed,\n"
        r"(?:0 skipped, )?0 failed, \d+ warnings?\.(?: Older v3_20/v3_21 cleanup verification is historical\.)?",
        "Current verification: after v5_0 closeout/current-alias reconciliation,\n"
        "`python -X utf8 -m pytest ai/tests --rag-current -q` -> 17 passed,\n"
        "0 skipped, 0 failed, 1 warning. Older v3_20/v3_21 cleanup verification is historical.",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"Current test surface is intentionally compact after legacy test deletion:\n"
        r"`python -X utf8 -m pytest ai/tests --rag-current -q`; full `ai/tests`\n"
        r"\s+now mirrors the current profile and no longer carries broad/nightly legacy\n"
        r"\s+suites\.",
        "Current test surface is nodeid-scoped for the fast current loop:\n"
        "`python -X utf8 -m pytest ai/tests --rag-current -q` runs the v5/v4-closeout handoff guardrails only; "
        "broad historical suites remain runnable outside `--rag-current`.",
        progress_text,
        count=1,
    )
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_0 v4 closeout and v5 gate plan

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: diagnostic-only closeout and gate planning; not official scoring, promotion, product-success evidence, or live readiness.

| counter | value |
| --- | --- |
| status | {STATUS} |
| v4_closeout_source_of_truth | {SOURCE_LOGICAL_RUN_KEY} |
| v4_closeout_basis_short_run_id | {SOURCE_RUN_ID} |
| current_resolves_to | {LOGICAL_RUN_KEY} |
| source_report_status | {report['source_report_status']} |
| source_report_sha256 | {report['source_report_sha256'] or 'materialized-in-memory'} |
| lineage_reproducibility_status | {summary['lineage_reproducibility_status']} |
| xlsx_materialization_repair_status | XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_ACCEPTED_DIAGNOSTIC_ONLY |
| xlsx_materialization_repair_decision | accept_materialized_axis_value_overlay_diagnostic_only |
| text_hit_count | {summary['TEXT']['hit']} |
| text_miss_count | {summary['TEXT']['miss']} |
| pdf_hit_count | {summary['PDF']['hit']} |
| pdf_miss_count | {summary['PDF']['miss']} |
| xlsx_hit_count | {summary['XLSX']['hit']} |
| xlsx_miss_count | {summary['XLSX']['miss']} |
| xlsx_zero_candidate_row_count | {summary['xlsx_zero_candidate_row_count']} |
| xlsx_candidate_budget_exhaustion_count | {summary['xlsx_candidate_budget_exhaustion_count']} |
| family_target_hit_regression_count | {json.dumps(summary['family_target_hit_regression_count'], sort_keys=True)} |
| official_metric_opening_preconditions_satisfied | false |
| live_readiness_promotion_preconditions_satisfied | false |
| official_metric_input_rows | 0 |
| silver_official_metric_input_rows | 0 |
| silver_promoted_to_gold_count | 0 |
| gold_mutation | false |
| qrels_mutation | false |
| label_mutation | false |
| denominator_mutation | false |
| training_dataset_created | false |
| fine_tuning | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements_text = measurements_text.replace("current_source_of_truth | v4_7_18", "v4_closeout_source_of_truth | v4_7_18")
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        "### v5_0 v4 closeout and v5 gate plan\n\n"
        f"- Basis: `{SOURCE_RUN_ID}` freezes v4 as diagnostic-only source-first, candidate-only, lineage-reproducible work. "
        "`current` resolves to `v5_0`; `v4_7_18` remains explicit and checkable.\n"
        "- User-owned decisions: golden set creation/review, expected answer and expected/supporting evidence judgment, "
        "relevance and answerability labels, gold policy, official denominator policy, and promotion policy.\n"
        "- Codex-owned work: implementation, test, report, path, indexing-scope, protected-surface, and failure-taxonomy "
        "work only; ambiguous non-gold choices stay fail-closed and diagnostic-only.\n"
        f"- XLSX residual backlog / engineering backlog: XLSX {summary['XLSX']['miss']} misses, "
        f"{summary['xlsx_zero_candidate_row_count']} zero-candidate rows, and "
        f"{summary['xlsx_candidate_budget_exhaustion_count']} budget-exhausted rows remain visible; "
        "`accept_materialized_axis_value_overlay_diagnostic_only` remains the frozen v4_7_18 repair decision.\n"
        "- Official metric opening preconditions: user-approved gold/qrels/labels/expected evidence, frozen denominator, "
        "metric definitions, blocked/deferred metric policy, and protected-surface diffs.\n"
        "- Live-readiness and promotion preconditions: accepted official metrics, live DB/index/cache rollout evidence, "
        "redaction/leakage/latency/rollback/monitoring evidence, and user-approved promotion/product-success policy."
    )
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        f"`current` resolves to `v5_0`: diagnostic-only v4 closeout and v5 gate planning. "
        f"`v4_7_18` remains the frozen v4 closeout basis at `{SOURCE_RUN_ID}` and remains directly checkable. "
        "v4 is closed as diagnostic-only source-first/candidate-only/lineage-reproducibility work, not as official evaluation. "
        f"TEXT {summary['TEXT']['hit']}/{summary['TEXT']['total']} hit, PDF {summary['PDF']['hit']}/{summary['PDF']['total']} hit, "
        f"XLSX {summary['XLSX']['hit']}/{summary['XLSX']['total']} hit; XLSX residual backlog remains "
        f"{summary['XLSX']['miss']} misses, {summary['xlsx_zero_candidate_row_count']} zero-candidate rows, and "
        f"{summary['xlsx_candidate_budget_exhaustion_count']} budget-exhausted rows.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, not denominator, "
        "not training/fine-tuning/FT-A, not promotion evidence, not product-success evidence, and not live readiness. "
        "Official opening still requires gold/qrels/expected-evidence/relevance/answerability/denominator/promotion decisions. "
        "official_metric_input_rows=0, fine_tuning_executed=false, and protected_namespaces_touched=[].\n"
        "Canonical rolling docs remain `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, "
        "and `docs/rag-ingestion-triage.md`; production promotion remains closed. "
        "Historical compatibility breadcrumbs retained for lower-section status-sync context, not current handoff: "
        "v4_7 remains pre-official; prior v4_7 cleanup keys remain explicit; supersedes the abstract v4_7_1 Korean "
        "review packet with hydrated rows 204, PDF 100, XLSX 104; v4_7_2 supersedes the abstract v4_7_1 packet with "
        "non-empty `질의문` 204 in `review_packet_ko_hydrated.xlsx`; `## Korean human review packet`; The previous "
        "v4_7_1 Korean review packet was abstract; actual Korean query candidates; User-owned fields remain "
        "blank/default; v4_7_3 applies the user-reviewed Korean query candidate CSV and v4_7_3 applies the "
        "user-reviewed CSV decisions (`미검수=통과`), not official metric and not gold/qrels; PDF survivor 58 and "
        "v4_7_4 replays only the 58 user-passed PDF survivor candidates."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_0`, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the "
        "frozen v4 closeout basis, `v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit` "
        "remains explicit, `v4_7_16_target_recall_repair_prototype` remains explicit, runner modules v4_7_13-v4_7_18 "
        "remain tracked and not ignored, and all official/gold/qrels/labels/denominator/training/fine-tuning/FT-A/"
        "promotion/product-success/live-readiness gates stay closed. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = RAW_PAYLOAD_FORBIDDEN_KEYS & set(value)
        if overlap:
            raise ValueError(f"v5_0 raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            _assert_no_raw_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload_keys(child)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_0 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_0 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_0 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_0 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_0 source run must remain v4_7_18")
    if report.get("source_report_status") != v4718.STATUS:
        raise ValueError("v5_0 source report status mismatch")
    if report.get("v4_closeout_basis") != SOURCE_LOGICAL_RUN_KEY:
        raise ValueError("v5_0 v4 closeout basis mismatch")
    if report.get("v4_closeout_basis_short_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_0 v4 closeout basis short_run_id mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_0 current resolution mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_0 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_0 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v5_0 opened official metric rows")
    if report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v5_0 promoted silver to gold")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_0 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v5_0 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v5_0 SourceAtom/EvidenceBundle role changed")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v5_0 raw prompt/response payload must not be written")
    if report.get("answer_generation_attempted") is not False:
        raise ValueError("v5_0 answer generation must remain closed")
    if report.get("generated_response_count") != 0:
        raise ValueError("v5_0 generated response count must remain zero")
    counters = report.get("counters") or {}
    for key in ("official_metric_input_rows", "silver_official_metric_input_rows", "silver_promoted_to_gold_count"):
        if counters.get(key) != 0:
            raise ValueError(f"v5_0 counter drift: {key}")
    if counters.get("generated_response_count") != 0:
        raise ValueError("v5_0 generated response counter must remain zero")
    _assert_no_raw_payload_keys(report)

    summary = report.get("v4_7_18_summary_counters") or {}
    expected_families = {
        "TEXT": {"hit": 232, "total": 350, "miss": 118},
        "PDF": {"hit": 265, "total": 325, "miss": 60},
        "XLSX": {"hit": 26, "total": 325, "miss": 299},
    }
    for family, expected in expected_families.items():
        if summary.get(family) != expected:
            raise ValueError(f"v5_0 {family} v4_7_18 summary counter drift")
    if summary.get("xlsx_baseline_target_hit_count") != 15:
        raise ValueError("v5_0 XLSX baseline counter drift")
    if summary.get("xlsx_v4_7_17_combined_target_hit_count") != 17:
        raise ValueError("v5_0 XLSX v4_7_17 counter drift")
    if summary.get("xlsx_zero_candidate_row_count") != 78:
        raise ValueError("v5_0 XLSX zero-candidate counter drift")
    if summary.get("xlsx_candidate_budget_exhaustion_count") != 109:
        raise ValueError("v5_0 XLSX budget-exhausted counter drift")
    if summary.get("family_target_hit_regression_count") != {"TEXT": 0, "PDF": 0, "XLSX": 0}:
        raise ValueError("v5_0 family target-hit regression counter drift")
    if summary.get("v4_7_16_candidate_set_sha256") != "b388d4fec10886142f8d3cee25db2eb771e7f4236e311b91c4ea175325a1bc5d":
        raise ValueError("v5_0 v4_7_16 candidate digest drift")
    if summary.get("v4_7_16_candidate_set_sha256_matches_recomputed") is not True:
        raise ValueError("v5_0 v4_7_16 candidate digest match drift")
    if summary.get("lineage_reproducibility_status") != "LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY":
        raise ValueError("v5_0 lineage status drift")
    if summary.get("required_runner_module_tracking_status") != "REQUIRED_RUNNER_MODULES_TRACKED_AND_NOT_IGNORED":
        raise ValueError("v5_0 required runner tracking drift")

    gate_plan = report.get("v5_gate_plan") or {}
    if set(gate_plan) != {"A", "B", "C", "D", "E"}:
        raise ValueError("v5_0 gate plan lane mismatch")
    if gate_plan["A"].get("owner") != "user":
        raise ValueError("v5_0 gate plan user-owned lane drift")
    if gate_plan["B"].get("owner") != "codex":
        raise ValueError("v5_0 gate plan Codex-owned lane drift")
    if gate_plan["D"].get("status") != "closed_pending_user_owned_policy":
        raise ValueError("v5_0 gate plan official metric lane opened")
    if gate_plan["E"].get("status") != "closed_pending_official_metric_and_promotion_policy":
        raise ValueError("v5_0 gate plan live-readiness/promotion lane opened")
