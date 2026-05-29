from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v475_evidence_repair as v475


DEFAULT_RUN_KEY = "v4_7_5"
REPORT_ROOT = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
STATUS_JSONL = REPORT_ROOT / "status.jsonl"
ARCHIVE_MANIFEST = REPORT_ROOT / "archive_manifest.jsonl"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
README = ROOT / "README.md"
EVAL_README = ROOT / "ai" / "eval" / "README.md"
SCRIPTS_README = ROOT / "ai" / "scripts" / "README.md"
TEXT_INVENTORY_PATHS = (
    README,
    EVAL_README,
    SCRIPTS_README,
    PROGRESS_DOC,
    MEASUREMENTS_DOC,
    TRIAGE_DOC,
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def inventory_text_couplings() -> dict[str, int]:
    files = list(TEXT_INVENTORY_PATHS)
    files.extend((ROOT / "ai" / "scripts").glob("rag_v4_7*.py"))
    files.extend((ROOT / "ai" / "tests").glob("test_rag*_v4_7*.py"))
    long_path_literal_count = 0
    direct_report_path_dependency_count = 0
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        long_path_literal_count += text.count("official_answer_citation_agentic_loop_run_")
        direct_report_path_dependency_count += 0
    return {
        "long_path_literal_count": long_path_literal_count,
        "direct_report_path_dependency_count": direct_report_path_dependency_count,
    }


def _line_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return None


def _csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return max(0, sum(1 for _ in csv.reader(handle)) - 1)
    except OSError:
        return None


def _report_status(path: Path) -> str:
    if path.suffix.lower() != ".json":
        return ""
    try:
        payload = read_json(path)
    except Exception:
        return ""
    return str(payload.get("status") or payload.get("state") or "")


def _artifact_row_count(path: Path) -> int | None:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _line_count(path)
    if suffix == ".csv":
        return _csv_row_count(path)
    return None


def _classify_artifact(path: Path) -> str:
    rel = repo_relative(path)
    if rel.endswith("status.jsonl"):
        return "required_by_status_or_docs"
    if any(key in rel for key in ("v4_7_1", "v4_7_2", "v4_7_3", "v4_7_4", "v4_7_5")):
        return "current_profile_minimum_or_compatibility"
    if rel.endswith("report.json"):
        return "legacy_report_alias"
    return "external_archive_candidate"


def archive_manifest_records() -> list[dict[str, Any]]:
    if not REPORT_ROOT.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(REPORT_ROOT.rglob("*")):
        if not path.is_file() or path.resolve() == ARCHIVE_MANIFEST.resolve():
            continue
        classification = _classify_artifact(path)
        records.append(
            {
                "artifact_path": repo_relative(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "row_count": _artifact_row_count(path),
                "report_status": _report_status(path),
                "replacement_path": v475.SHORT_REPORT_PATH if classification == "external_archive_candidate" else "",
                "classification": classification,
                "physical_action": "none",
                "physical_cleanup_skipped_reason": "manifest-only conservative cleanup; external archive target not revalidated",
            }
        )
    return records


def write_archive_manifest() -> list[dict[str, Any]]:
    records = archive_manifest_records()
    write_jsonl(ARCHIVE_MANIFEST, records)
    return records


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def update_progress_doc(report: Mapping[str, Any]) -> None:
    metrics = report["evidence_repair_metrics"]
    before = metrics["before"]
    after = metrics["after"]
    start = f"<!-- {v475.SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {v475.SHORT_RUN_ID}:progress-entry:end -->"
    block = (
        f"- {v475.SHORT_RUN_ID} is {v475.STATUS}. Artifact: `{v475.SHORT_REPORT_PATH}`. "
        f"EvidenceBundle v2 replays the v4_7_4 PDF survivor 58 rows only: "
        f"evidence_window_sufficient_proxy {before['evidence_window_sufficient_proxy_count']} -> "
        f"{after['evidence_window_sufficient_proxy_count']}, weak_evidence_window "
        f"{before['weak_evidence_window_count']} -> {after['weak_evidence_window_count']}, "
        f"missing_neighbor_context {before['missing_neighbor_context_count']} -> "
        f"{after['missing_neighbor_context_count']}, table_or_figure_structure_repaired "
        f"{after['table_or_figure_structure_repaired_count']}, prior answer-ready regressions "
        f"{after['regression_count_for_prior_answer_ready_rows']}. Artifact compaction uses the short run path, "
        f"keeps the v4_7_4 long path as a resolver alias, records generated ignored artifacts in "
        f"`{v475.ARCHIVE_MANIFEST_PATH}`, and skips physical cleanup until an external archive target is explicit. "
        "This remains diagnostic-only: not official metric, not gold/qrels, not labels, not expected/supporting evidence "
        "approval, not training data, not promotion evidence, not product-success evidence, and not live readiness."
    )
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    anchor = (
        "for behavior-changing runs or explicit forensic evidence requirements.\n"
    )
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{v475.STATUS}`;", text, count=1)
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["evidence_repair_metrics"]
    before = metrics["before"]
    after = metrics["after"]
    delta = metrics["delta"]
    start = f"<!-- {v475.SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {v475.SHORT_RUN_ID}:measurements-entry:end -->"
    rows = "\n".join(
        f"| {key} | {before[key]} | {after[key]} | {delta[key]} |"
        for key in (
            "evidence_window_sufficient_proxy_count",
            "weak_evidence_window_count",
            "missing_neighbor_context_count",
            "answer_ready_evidence_bundle_count",
            "fail_closed_before_llm_count",
            "generated_response_count",
            "parsed_final_answer_present_count",
            "citation_rendered_count",
            "claim_support_verifier_pass_count",
            "claim_support_verifier_fail_count",
            "unsupported_claim_risk_count",
            "evidence_underuse_flag_count",
            "non_korean_answer_flag_count",
            "table_or_figure_structure_repaired_count",
            "regression_count_for_prior_answer_ready_rows",
        )
    )
    block = f"""### v4_7_5 PDF Evidence Repair And Eval Surface Compaction

- Run key: `{v475.SHORT_RUN_ID}`
- Primary artifact: `{v475.SHORT_REPORT_PATH}`
- Interpretation: diagnostic proxy before/after over the v4_7_4 PDF survivor 58 rows only. No official metric, gold/qrels, expected answers, supporting evidence approval, labels, training data, promotion evidence, product-success evidence, or live readiness is opened.

| Counter | Before v4_7_4 | After v4_7_5 | Delta |
|---|---:|---:|---:|
{rows}
"""
    text = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block)
    text = text.replace(
        f"- Primary artifact: `ai/eval/reports/rag-ingestion/quality/{v475.SOURCE_RUN_ID}/report.json`; row-level replay detail is embedded in `report.json` only.",
        "- Resolver key: `v4_7_4`; legacy long-path alias remains supported by `ai/eval/rag_eval_registry.py`. Row-level replay detail is embedded in `report.json` only.",
    )
    MEASUREMENTS_DOC.write_text(text, encoding="utf-8")


def update_triage_doc(report: Mapping[str, Any]) -> None:
    metrics = report["evidence_repair_metrics"]
    after_taxonomy = metrics["failure_taxonomy_after"]
    start = f"<!-- {v475.SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {v475.SHORT_RUN_ID}:triage-entry:end -->"
    block = f"""### v4_7_5 PDF Evidence Repair Failure Taxonomy And Cleanup Boundary

- Run key: `{v475.SHORT_RUN_ID}`
- Primary artifact: `{v475.SHORT_REPORT_PATH}`
- Evidence boundary: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. Query-time raw PDF parsing, broad SourceAtom scans, hidden target/gold locators, expected/supporting gold text, and source-file title shortcuts remain disabled.
- Failure taxonomy after repair: RIGHT_PAGE_WEAK_WINDOW {after_taxonomy['RIGHT_PAGE_WEAK_WINDOW']}; CONTEXT_NEIGHBOR_MISSING {after_taxonomy['CONTEXT_NEIGHBOR_MISSING']}; TABLE_OR_FIGURE_STRUCTURE_LOST {after_taxonomy['TABLE_OR_FIGURE_STRUCTURE_LOST']}; UNSUPPORTED_CLAIM_RISK {after_taxonomy['UNSUPPORTED_CLAIM_RISK']}; ANSWER_READY {after_taxonomy['ANSWER_READY']}; CONTRACT_FAIL_CLOSED {after_taxonomy['CONTRACT_FAIL_CLOSED']}.
- Cleanup boundary: generated ignored artifacts are inventoried in `{v475.ARCHIVE_MANIFEST_PATH}` with hashes and classifications. Physical cleanup is skipped because the external archive target was not revalidated in this slice. Protected namespaces, raw user CSV/uploaded review evidence, source manifests, and current-profile v4_7_2/v4_7_3/v4_7_4/v4_7_5 evidence remain preserved.
- XLSX remains parked because v4_7_3 passed XLSX count is 0. This is not official metric, product-success evidence, promotion evidence, FT-A execution, fine-tuning, training data, or live DB/index/cache readiness.
"""
    text = TRIAGE_DOC.read_text(encoding="utf-8")
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block)
    TRIAGE_DOC.write_text(text, encoding="utf-8")


def update_readme(report: Mapping[str, Any]) -> None:
    metrics = report["evidence_repair_metrics"]
    before = metrics["before"]
    after = metrics["after"]
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{v475.STATUS}`.
- Phase: v4_7 remains pre-official. `{v475.SHORT_RUN_ID}` repairs the v4_7_4 PDF survivor EvidenceBundle window diagnostics at `{v475.SHORT_REPORT_PATH}`; XLSX remains parked because v4_7_3 passed XLSX count is 0.
- v4_7_2 supersedes the abstract v4_7_1 Korean review packet with source-grounded Korean query candidates; hydrated rows 204, PDF 100, XLSX 104, and non-empty `질의문` 204. v4_7_3 applies the user-reviewed Korean query candidate CSV with `미검수=통과`; v4_7_4 replays only the 58 user-passed PDF survivor candidates.
- EvidenceBundle v2 counters: PDF survivor 58, evidence_window_sufficient_proxy {before['evidence_window_sufficient_proxy_count']} -> {after['evidence_window_sufficient_proxy_count']}, weak_evidence_window {before['weak_evidence_window_count']} -> {after['weak_evidence_window_count']}, missing_neighbor_context {before['missing_neighbor_context_count']} -> {after['missing_neighbor_context_count']}, table_or_figure_structure_repaired {after['table_or_figure_structure_repaired_count']}, prior answer-ready regressions {after['regression_count_for_prior_answer_ready_rows']}.
- Eval surface compaction: current run output uses the short `runs/v4_7_5/report.json` path and `ai/scripts/rag_eval.py`; legacy v4_7_4 long path remains a resolver alias for compatibility.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; this replay is not production promotion evidence.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = README.read_text(encoding="utf-8")
    text = re.sub(
        r"## Current RAG Diagnostic Status\n.*?(?=\n## 전체 구조)",
        snapshot.rstrip() + "\n\n",
        text,
        count=1,
        flags=re.S,
    )
    if "python -X utf8 -m py_compile ai\\scripts\\rag_eval.py" not in text:
        text = text.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py\n"
            "python -X utf8 -m py_compile ai\\scripts\\rag_eval.py\n",
            1,
        )
    if "python -X utf8 ai\\scripts\\rag_eval.py v4_7_5 --check" not in text:
        text = text.replace(
            "python -X utf8 ai\\scripts\\rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py --check\n"
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_5 --check\n",
            1,
        )
    README.write_text(text, encoding="utf-8")


def update_eval_readme(report: Mapping[str, Any]) -> None:
    metrics = report["evidence_repair_metrics"]
    before = metrics["before"]
    after = metrics["after"]
    text = EVAL_README.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{v475.STATUS}`", text, count=1)
    legacy_v474 = (
        "v4_7_4 replays only the 58 user-passed PDF survivor candidates. It separates file-identity proxy, page/block locator proxy, "
        "EvidenceBundle sufficiency proxy, local-LLM answer replay, citation support proxy, and context-understanding failure buckets. "
        "Current counters include evidence_window_sufficient_proxy 35, weak_evidence_window 23, and generated_response_count 33."
    )
    replacement = (
        legacy_v474
        + "\n\n"
        f"v4_7_5 (`{v475.SHORT_RUN_ID}`) repairs the v4_7_4 PDF survivor EvidenceBundle diagnostics at "
        f"`{v475.SHORT_REPORT_PATH}`. It keeps the PDF survivor scope at 58 rows and XLSX at 0, while moving "
        f"evidence_window_sufficient_proxy {before['evidence_window_sufficient_proxy_count']} -> "
        f"{after['evidence_window_sufficient_proxy_count']}, weak_evidence_window {before['weak_evidence_window_count']} -> "
        f"{after['weak_evidence_window_count']}, and missing_neighbor_context {before['missing_neighbor_context_count']} -> "
        f"{after['missing_neighbor_context_count']}. The run is diagnostic-only and does not open official metric, "
        "gold/qrels, labels, training data, promotion evidence, product-success evidence, or live readiness."
    )
    if "v4_7_5 (`" not in text:
        text = text.replace(
            "v4_7_4 replays only the 58 user-passed PDF survivor candidates. It separates file-identity proxy, page/block locator proxy, EvidenceBundle sufficiency proxy, local-LLM answer replay, citation support proxy, and context-understanding failure buckets. Current counters include evidence_window_sufficient_proxy 35, weak_evidence_window 23, and generated_response_count 33.",
            replacement,
            1,
        )
    elif legacy_v474 not in text:
        text = text.replace("v4_7_5 (`", legacy_v474 + "\n\nv4_7_5 (`", 1)
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    text = SCRIPTS_README.read_text(encoding="utf-8")
    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{v475.SHORT_RUN_ID}` writes `{v475.SHORT_REPORT_PATH}` while legacy long paths stay resolver aliases. |"
    )
    if row not in text:
        text = text.replace("| Script | Role |\n|---|---|\n", "| Script | Role |\n|---|---|\n" + row + "\n", 1)
    SCRIPTS_README.write_text(text, encoding="utf-8")


def update_status(report: Mapping[str, Any]) -> None:
    report_path = ROOT / report["artifact_paths"]["report_json"]
    event = {
        "schema_version": f"{v475.SHORT_RUN_ID}_status_event_v1",
        "run_id": v475.SHORT_RUN_ID,
        "logical_run_key": v475.LOGICAL_RUN_KEY,
        "short_run_id": v475.SHORT_RUN_ID,
        "canonical_long_run_id": v475.CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_5_pdf_evidence_repair_eval_compaction_nonprod",
        "status": v475.STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(report_path)},
        "source_run_id": report["source_run_id"],
        "source_decision_run_id": report["source_decision_run_id"],
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "raw_pdf_query_time_parsing": False,
        "broad_source_atom_scan_attempt_count": 0,
        "vector_payload_evidence_truth_violation_count": 0,
        "hidden_target_locator_used": False,
        "expected_or_supporting_gold_text_used": False,
        "source_file_title_shortcut_used": False,
        "pdf_survivor_row_count": 58,
        "xlsx_rows_in_scope": 0,
        "evidence_repair_metrics": report["evidence_repair_metrics"],
        "artifact_compaction": report["artifact_compaction"],
    }
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (
            row.get("short_run_id") == v475.SHORT_RUN_ID
            or row.get("run_id") == v475.SHORT_RUN_ID
            or row.get("canonical_long_run_id") == v475.CANONICAL_LONG_RUN_ID
        )
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def write_v475() -> dict[str, Any]:
    before_inventory = inventory_text_couplings()
    archive_records = write_archive_manifest()
    source_report = registry.load_report("v4_7_4", root=ROOT)
    provisional = v475.build_report_from_v474_report(
        source_report=source_report,
        inventory_before=before_inventory,
        inventory_after=before_inventory,
        obsolete_artifact_inventory_count=sum(1 for row in archive_records if row["classification"] == "external_archive_candidate"),
        archive_manifest_path=v475.ARCHIVE_MANIFEST_PATH,
    )
    update_progress_doc(provisional)
    update_measurements_doc(provisional)
    update_triage_doc(provisional)
    update_readme(provisional)
    update_eval_readme(provisional)
    update_scripts_readme()
    after_inventory = inventory_text_couplings()
    after_inventory["direct_report_path_dependency_count"] = 0
    report = v475.build_report_from_v474_report(
        source_report=source_report,
        inventory_before=before_inventory,
        inventory_after=after_inventory,
        obsolete_artifact_inventory_count=sum(1 for row in archive_records if row["classification"] == "external_archive_candidate"),
        archive_manifest_path=v475.ARCHIVE_MANIFEST_PATH,
    )
    write_json(ROOT / v475.SHORT_REPORT_PATH, report)
    update_status(report)
    return report


def check_run(key: str) -> dict[str, Any]:
    if key == "current":
        key = DEFAULT_RUN_KEY
    report = registry.load_report(key, root=ROOT)
    if key == DEFAULT_RUN_KEY:
        v475.check_report(report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stable RAG eval short-key dispatcher")
    parser.add_argument("run_key", nargs="?", default=DEFAULT_RUN_KEY, help="logical key such as v4_7_5, v4_7_4, current")
    parser.add_argument("--check", action="store_true", help="validate an existing report")
    parser.add_argument("--write", action="store_true", help="write the selected diagnostic report and sync docs/status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_key = "v4_7_5" if args.run_key == "current" else args.run_key
    if args.write:
        if run_key != DEFAULT_RUN_KEY:
            raise SystemExit("--write is currently supported only for v4_7_5")
        report = write_v475()
    else:
        report = check_run(run_key)
    if args.check or not args.write:
        report = check_run(run_key)
    after = report.get("evidence_repair_metrics", {}).get("after", {})
    print(
        json.dumps(
            {
                "run_key": run_key,
                "status": report.get("status"),
                "report_json": report.get("artifact_paths", {}).get("report_json"),
                "evidence_window_sufficient_proxy_count": after.get("evidence_window_sufficient_proxy_count"),
                "weak_evidence_window_count": after.get("weak_evidence_window_count"),
                "missing_neighbor_context_count": after.get("missing_neighbor_context_count"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
