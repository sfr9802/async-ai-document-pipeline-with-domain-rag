from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_7"
SHORT_RUN_ID = "v4_7_7_v3_legacy_archive_and_runner_consolidation"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_7_"
    "v3_legacy_artifact_archive_and_diagnostic_runner_consolidation_nonprod"
)
STATUS = "V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
V3_LEGACY_MANIFEST_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "v3_legacy_artifact_manifest.jsonl"
ARCHIVE_MANIFEST_PATH = REPORT_ROOT / "archive_manifest.jsonl"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
V476_CLEANUP_MANIFEST_PATH = REPORT_ROOT / "runs" / "v4_7_6" / "cleanup_manifest.jsonl"

SAFE_LEGACY_CHECK_ALIASES = ("v3_21", "v3_22")
HELD_LEGACY_ENTRYPOINTS = {
    "v3_16": "check-only runtime was not folded because the direct --check run exceeded the safe wrapper timeout",
    "v3_9_2_to_v3_20": "kept as explicit legacy entrypoints until each check-only path is individually verified",
    "retrieval_or_promotion_scripts": "not folded into the current runner because v4_7_7 is cleanup-only",
}

V3_LEGACY_RE = re.compile(
    r"(official_answer_citation_agentic_loop_run_v3(?:_|$)|pdf_xlsx_answer_quality_review_packet_v3(?:_|$)|v3_[0-9])"
)
REQUIRED_FALSE_KEYS = (
    "official_metric",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "training_dataset_created",
    "ft_a_execution",
    "fine_tuning",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
)


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def _repo_path(root: Path, rel: Path) -> Path:
    return root / rel


def _as_repo_rel_text(path: Path) -> str:
    return path.as_posix()


def is_v3_legacy_artifact_rel(rel: Path) -> bool:
    text = rel.as_posix()
    if not text.startswith(REPORT_ROOT.as_posix() + "/"):
        return False
    if text.startswith((REPORT_ROOT / "runs" / LOGICAL_RUN_KEY).as_posix() + "/"):
        return False
    return bool(V3_LEGACY_RE.search(text))


def local_v3_legacy_artifacts(root: Path) -> list[Path]:
    report_root = root / REPORT_ROOT
    if not report_root.exists():
        return []
    candidates: list[Path] = []
    for path in report_root.rglob("*"):
        if not path.is_file():
            continue
        rel = Path(v476.repo_relative(path, root))
        if is_v3_legacy_artifact_rel(rel):
            candidates.append(path)
    return sorted(candidates, key=lambda item: v476.repo_relative(item, root))


def _existing_v476_archived_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in v476.read_jsonl(root / V476_CLEANUP_MANIFEST_PATH):
        rel_text = str(row.get("original_relative_path") or "")
        if not rel_text:
            continue
        rel = Path(rel_text)
        if not is_v3_legacy_artifact_rel(rel):
            continue
        if row.get("classification") != "ARCHIVE_THEN_REMOVE" or not row.get("removed_from_repo_at"):
            continue
        if (root / rel).exists():
            continue
        rows.append(
            {
                "original_relative_path": _as_repo_rel_text(rel),
                "classification": "EXTERNALLY_ARCHIVED_REMOVED",
                "reason": "v4_7_6 archived the generated v3 legacy artifact externally and removed the repo-local copy",
                "hold_reason": "",
                "size_bytes": int(row.get("size_bytes") or 0),
                "sha256": str(row.get("sha256") or ""),
                "archive_copy_verified": bool(row.get("archive_copy_verified")),
                "removed_from_repo_at": str(row.get("removed_from_repo_at") or ""),
                "archive_path_redacted": True,
                "source_cleanup_run_id": "v4_7_6_eval_artifact_archive_purge",
            }
        )
    return rows


def _local_hold_classification(rel: Path) -> tuple[str, str]:
    text = rel.as_posix()
    if "/quality/pdf_xlsx_answer_quality_review_packet_v3_9" in text:
        return (
            "EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET",
            "documented answer-quality review packet is still referenced by current docs/tests",
        )
    if "/quality/official_answer_citation_agentic_loop_run_v3_" in text:
        return (
            "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT",
            "current RAG tests or docs still read this legacy quality artifact",
        )
    if rel.parent == REPORT_ROOT and rel.name.startswith("official_answer_citation_agentic_loop_run_v3_"):
        return (
            "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT",
            "current RAG tests still resolve this compact root-level legacy artifact",
        )
    return (
        "EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE",
        "generated-looking v3 legacy artifact needs a narrower owner decision before deletion",
    )


def _local_hold_row(path: Path, *, root: Path) -> dict[str, Any]:
    rel = Path(v476.repo_relative(path, root))
    classification, hold_reason = _local_hold_classification(rel)
    return {
        "original_relative_path": _as_repo_rel_text(rel),
        "classification": classification,
        "reason": "repo-local generated v3 legacy artifact is retained explicitly instead of silently deleting it",
        "hold_reason": hold_reason,
        "size_bytes": path.stat().st_size,
        "sha256": v476.sha256_file(path),
        "archive_copy_verified": False,
        "removed_from_repo_at": "",
        "archive_path_redacted": True,
        "source_cleanup_run_id": "",
    }


def build_v3_legacy_manifest(root: Path) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _existing_v476_archived_rows(root):
        merged[(str(row["original_relative_path"]), str(row["classification"]))] = row
    for path in local_v3_legacy_artifacts(root):
        row = _local_hold_row(path, root=root)
        merged[(str(row["original_relative_path"]), str(row["classification"]))] = row
    return [merged[key] for key in sorted(merged)]


def _count_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    rows = list(rows)
    archived_or_removed = sum(
        1
        for row in rows
        if row.get("classification") in {"EXTERNALLY_ARCHIVED_REMOVED", "ARCHIVE_THEN_REMOVE"}
        and (row.get("sha256") or row.get("removed_from_repo_at"))
    )
    deleted = sum(1 for row in rows if row.get("classification") == "DELETE_ONLY" and row.get("deleted_at"))
    manual_hold = sum(1 for row in rows if str(row.get("classification") or "").startswith("EXPLICIT_HOLD"))
    unclassified = sum(1 for row in rows if not row.get("classification"))
    return {
        "artifact_count": len(rows),
        "archived_or_removed": archived_or_removed,
        "deleted": deleted,
        "manual_hold": manual_hold,
        "unclassified": unclassified,
    }


def _hold_counts_by_classification(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        classification = str(row.get("classification") or "")
        if not classification.startswith("EXPLICIT_HOLD"):
            continue
        counts[classification] = counts.get(classification, 0) + 1
    return dict(sorted(counts.items()))


def _script_consolidation() -> dict[str, Any]:
    return {
        "stable_runner": "ai/scripts/rag_eval.py",
        "safe_check_aliases": list(SAFE_LEGACY_CHECK_ALIASES),
        "held_legacy_entrypoints": dict(HELD_LEGACY_ENTRYPOINTS),
        "new_per_run_script_created": False,
        "retrieval_promotion_scripts_folded_into_current": False,
        "runner_scope": "check-only aliases for individually verified legacy diagnostics; v4_7_7 write stays cleanup-only",
    }


def _status_event(report: Mapping[str, Any], *, report_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_7_v3_legacy_archive_runner_consolidation_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": report_sha256},
        "diagnostic_only": True,
        "non_production": True,
        "cleanup_only": True,
        "archive_aware_eval_surface": True,
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
        "v3_legacy_artifact_count": report["v3_legacy_artifact_count"],
        "v3_legacy_archived_or_removed_count": report["v3_legacy_archived_or_removed_count"],
        "v3_legacy_deleted_count": report["v3_legacy_deleted_count"],
        "v3_legacy_manual_hold_count": report["v3_legacy_manual_hold_count"],
        "v3_legacy_unclassified_count": report["v3_legacy_unclassified_count"],
        "v3_legacy_hold_counts_by_classification": report["v3_legacy_hold_counts_by_classification"],
        "script_consolidation": report["script_consolidation"],
    }


def append_status(root: Path, report: Mapping[str, Any], *, report_sha256: str) -> None:
    status_path = root / STATUS_JSONL_PATH
    existing = [
        row
        for row in v476.read_jsonl(status_path)
        if row.get("short_run_id") != SHORT_RUN_ID and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
    ]
    v476.write_jsonl(status_path, [*existing, _status_event(report, report_sha256=report_sha256)])


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    return v476.upsert_block(text, start_marker=start_marker, end_marker=end_marker, block=block, after_anchor=after_anchor)


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    start = f"<!-- {SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:progress-entry:end -->"
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        "This is cleanup/refactor only: the current resolver moves to short key `v4_7_7`, "
        "v3 legacy generated report artifacts are classified as externally archived/removed or explicit holds, "
        f"and the stable runner now exposes safe check aliases {', '.join(SAFE_LEGACY_CHECK_ALIASES)}. "
        f"Manifest counters: total {report['v3_legacy_artifact_count']}, archived/removed "
        f"{report['v3_legacy_archived_or_removed_count']}, deleted {report['v3_legacy_deleted_count']}, "
        f"held {report['v3_legacy_manual_hold_count']} "
        f"({', '.join(f'{key}={value}' for key, value in report['v3_legacy_hold_counts_by_classification'].items())}), "
        f"unclassified {report['v3_legacy_unclassified_count']}. "
        "Protected namespaces remain untouched. This does not run retrieval, EvidenceBundle repair, LLM answer "
        "generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, "
        "training, FT-A, fine_tuning, promotion, product-success, or live readiness."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    anchor = "for behavior-changing runs or explicit forensic evidence requirements.\n"
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    start = f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->"
    block = f"""### v4_7_7 V3 Legacy Archive And Runner Consolidation

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: archive-aware cleanup/refactor counters only. No retrieval, EvidenceBundle, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Value |
|---|---:|
| v3_legacy_artifact_count | {report['v3_legacy_artifact_count']} |
| v3_legacy_archived_or_removed_count | {report['v3_legacy_archived_or_removed_count']} |
| v3_legacy_deleted_count | {report['v3_legacy_deleted_count']} |
| v3_legacy_manual_hold_count | {report['v3_legacy_manual_hold_count']} |
| v3_legacy_unclassified_count | {report['v3_legacy_unclassified_count']} |
| safe_runner_check_alias_count | {len(report['script_consolidation']['safe_check_aliases'])} |
| hold_current_test_or_doc_contract | {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)} |
| hold_documented_legacy_review_packet | {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET', 0)} |
| hold_ambiguous_generated_surface | {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)} |
"""
    text = path.read_text(encoding="utf-8")
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    block = f"""### v4_7_7 V3 Legacy Archive And Runner Consolidation

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- EXTERNALLY_ARCHIVED_REMOVED: v4_7_6 verified archive copies and removed repo-local generated v3 artifacts.
- EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT: repo-local v3 artifacts still read by current tests/docs remain held with reasons.
- EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET: documented legacy review packet surfaces remain held until their readers move.
- Runner consolidation: `ai/scripts/rag_eval.py` owns the current short key plus safe check aliases `v3_21` and `v3_22`; `v3_16` and older unverified legacy entrypoints remain explicit holds.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
- Held count: {report['v3_legacy_manual_hold_count']}; held breakdown: current test/doc contract {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)}, documented review packet {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET', 0)}, ambiguous generated surface {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)}. Unclassified count: {report['v3_legacy_unclassified_count']}.
"""
    text = path.read_text(encoding="utf-8")
    text = _upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` is cleanup/refactor only and writes `{SHORT_REPORT_PATH.as_posix()}`; it does not replay retrieval, EvidenceBundle, or answer generation.
- Resolver wiring: use `current` or `v4_7_7` for the latest archive-aware cleanup report, `v4_7_6` for the previous archive purge report, and short lineage keys `v4_7_preofficial`, `v4_7_2`, `v4_7_3`, `v4_7_4`, and `v4_7_5` for preserved current-profile provenance.
- v3 legacy artifact policy: generated v3 report artifacts are now classified in `{V3_LEGACY_MANIFEST_PATH.as_posix()}` as externally archived/removed, deleted, or explicit holds with reasons. Counters are total {report['v3_legacy_artifact_count']}, archived/removed {report['v3_legacy_archived_or_removed_count']}, deleted {report['v3_legacy_deleted_count']}, held {report['v3_legacy_manual_hold_count']} (current test/doc contract {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)}, documented review packet {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET', 0)}, ambiguous generated surface {report['v3_legacy_hold_counts_by_classification'].get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)}), unclassified {report['v3_legacy_unclassified_count']}.
- Runner consolidation: `ai/scripts/rag_eval.py` is the stable short-key runner. It owns `current`, `v4_7_7`, `v4_7_6`, and safe legacy check aliases `v3_21` and `v3_22`; unverified legacy diagnostic entrypoints remain explicit holds rather than being silently folded.
- v4_7 lineage preserved: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with source-grounded Korean query candidates, hydrated rows 204, PDF 100, XLSX 104, and non-empty `질의문` 204; v4_7_3 applies the user-reviewed Korean query candidate CSV with `미검수=통과`; v4_7_4 replays PDF survivor 58 rows only; v4_7_5 repairs the PDF survivor EvidenceBundle diagnostic window.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; no per-run Markdown is created.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## 전체 구조)", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    if "python -X utf8 ai\\scripts\\rag_eval.py v4_7_7 --check" not in text:
        text = text.replace(
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_6 --check\n",
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_6 --check\n"
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_7 --check\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path) -> None:
    path = root / "ai" / "eval" / "README.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    marker = (
        f"- v4_7_7 archive-aware cleanup/refactor: `{SHORT_RUN_ID}` writes "
        f"`{SHORT_REPORT_PATH.as_posix()}` through `ai/scripts/rag_eval.py`; use resolver key `current` "
        "for v4_7_7, `v4_7_6` for the prior archive purge, and safe legacy check aliases `v3_21`/`v3_22` "
        "only for verified check-only diagnostics."
    )
    if marker not in text:
        text = re.sub(
            r"(- v4_7_6 cleanup/refactor: .*?\n)",
            r"\1" + marker + "\n",
            text,
            count=1,
        )
        if marker not in text:
            text = text.replace(f"- Current RAG status: `{STATUS}`", f"- Current RAG status: `{STATUS}`\n{marker}", 1)
    text = text.replace(
        "v4_7_6 cleanup/refactor: `v4_7_6_eval_artifact_archive_purge` writes "
        "`reports/rag_eval/rag-ingestion/runs/v4_7_6/report.json` through `ai/scripts/rag_eval.py`; "
        "use resolver key `current` for this report and short lineage keys for "
        "v4_7_preofficial/v4_7_2/v4_7_3/v4_7_4/v4_7_5 provenance.",
        "v4_7_6 cleanup/refactor: `v4_7_6_eval_artifact_archive_purge` writes "
        "`reports/rag_eval/rag-ingestion/runs/v4_7_6/report.json` through `ai/scripts/rag_eval.py`; "
        "use resolver key `v4_7_6` for this prior archive-purge report and short lineage keys for "
        "v4_7_preofficial/v4_7_2/v4_7_3/v4_7_4/v4_7_5 provenance.",
    )
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path) -> None:
    path = root / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}`, `current` resolves to `v4_7_7`, "
        "and safe legacy check aliases `v3_21`/`v3_22` are available while unverified v3 entrypoints remain explicit holds. |"
    )
    text = re.sub(r"\| `rag_eval\.py` \| .*? \|", replacement, text, count=1)
    if replacement not in text:
        text = text.replace("| Script | Role |\n|---|---|\n", "| Script | Role |\n|---|---|\n" + replacement + "\n", 1)
    path.write_text(text, encoding="utf-8")


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    update_progress_doc(root, report)
    update_measurements_doc(root, report)
    update_triage_doc(root, report)
    update_root_readme(root, report)
    update_eval_readme(root)
    update_scripts_readme(root)


def build_report(
    *,
    root: Path,
    execute: bool,
    generated_at: str | None = None,
    sync_surfaces: bool = False,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now_iso()
    manifest_rows = build_v3_legacy_manifest(root)
    counts = _count_rows(manifest_rows)
    hold_counts = _hold_counts_by_classification(manifest_rows)
    target = v476.resolve_external_archive_target(root=root)
    report: dict[str, Any] = {
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "v3_legacy_manifest_jsonl": V3_LEGACY_MANIFEST_PATH.as_posix(),
            "archive_manifest_jsonl": ARCHIVE_MANIFEST_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        },
        "diagnostic_only": True,
        "non_production": True,
        "cleanup_only": True,
        "archive_aware_eval_surface": True,
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
        "external_archive_target_resolved": target.resolved,
        "external_archive_target_redacted": True,
        "external_archive_target_kind": target.source if target.resolved else "unresolved",
        "previous_cleanup_short_run_id": "v4_7_6_eval_artifact_archive_purge",
        "current_previous_key": "v4_7_6",
        "current_lineage_short_path_migrated": all(
            registry.resolve_run(key, root=root).report_path.exists()
            for key in ("v4_7_preofficial", "v4_7_2", "v4_7_3", "v4_7_4", "v4_7_5", "v4_7_6")
        ),
        "resolver_current_key_valid": registry.resolve_run("current", root=root).logical_key == LOGICAL_RUN_KEY,
        "v3_legacy_artifact_count": counts["artifact_count"],
        "v3_legacy_archived_or_removed_count": counts["archived_or_removed"],
        "v3_legacy_deleted_count": counts["deleted"],
        "v3_legacy_manual_hold_count": counts["manual_hold"],
        "v3_legacy_unclassified_count": counts["unclassified"],
        "v3_legacy_hold_counts_by_classification": hold_counts,
        "archive_copy_failed_count": sum(1 for row in manifest_rows if row.get("classification") == "ARCHIVE_COPY_FAILED"),
        "hash_verification_failed_count": sum(
            1
            for row in manifest_rows
            if row.get("archive_sha256") and row.get("sha256") and row.get("archive_sha256") != row.get("sha256")
        ),
        "script_consolidation": _script_consolidation(),
        "new_per_run_script_created": False,
        "dry_run": not execute,
        "residual_risks": [
            "held v3 legacy artifacts remain repo-local where tests or docs still read them",
            "unverified legacy diagnostics remain direct entrypoints instead of stable-runner aliases",
            "metrics remain cleanup counters only, not answer quality or official retrieval metrics",
        ],
    }
    if execute:
        v476.write_jsonl(root / V3_LEGACY_MANIFEST_PATH, manifest_rows)
    if sync_surfaces:
        update_docs(root, report)
    return report


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_7 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_7 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_7 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("cleanup_only") is not True:
        raise ValueError("v4_7_7 cleanup-only flags mismatch")
    if report.get("archive_aware_eval_surface") is not True:
        raise ValueError("v4_7_7 archive-aware eval surface flag missing")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_7 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_7 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_7 protected namespaces were touched")
    if report.get("v3_legacy_unclassified_count") != 0:
        raise ValueError("v4_7_7 v3 legacy artifacts must not remain unclassified")
    total = report.get("v3_legacy_artifact_count")
    counted = (
        report.get("v3_legacy_archived_or_removed_count", 0)
        + report.get("v3_legacy_deleted_count", 0)
        + report.get("v3_legacy_manual_hold_count", 0)
    )
    if total != counted:
        raise ValueError("v4_7_7 v3 legacy classification counts do not sum to total")
    if report.get("archive_copy_failed_count") != 0:
        raise ValueError("v4_7_7 archive copy failure present")
    if report.get("hash_verification_failed_count") != 0:
        raise ValueError("v4_7_7 hash verification failure present")
    hold_counts = report.get("v3_legacy_hold_counts_by_classification") or {}
    if sum(int(value) for value in hold_counts.values()) != report.get("v3_legacy_manual_hold_count"):
        raise ValueError("v4_7_7 hold classification counts do not sum to manual hold count")
    consolidation = report.get("script_consolidation") or {}
    if consolidation.get("stable_runner") != "ai/scripts/rag_eval.py":
        raise ValueError("v4_7_7 stable runner mismatch")
    if "v3_22" not in consolidation.get("safe_check_aliases", ()):
        raise ValueError("v4_7_7 v3_22 safe alias missing")
    if "v3_16" not in consolidation.get("held_legacy_entrypoints", {}):
        raise ValueError("v4_7_7 v3_16 hold reason missing")
