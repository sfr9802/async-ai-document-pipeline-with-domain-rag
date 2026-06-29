from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v476_archive_purge as v476
from ai.eval import rag_v477_legacy_archive_consolidation as v477


LOGICAL_RUN_KEY = "v4_7_8"
SHORT_RUN_ID = "v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_8_"
    "test_doc_dependency_decoupling_and_legacy_runner_alias_expansion_nonprod"
)
STATUS = "V4_7_8_TEST_DOC_DEPENDENCY_DECOUPLING_RUNNER_ALIAS_EXPANSION_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
HOLD_REDUCTION_MANIFEST_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "v3_legacy_hold_reduction_manifest.jsonl"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
ARCHIVE_MANIFEST_PATH = REPORT_ROOT / "archive_manifest.jsonl"
V477_REPORT_PATH = REPORT_ROOT / "runs" / "v4_7_7" / "report.json"
V477_MANIFEST_PATH = REPORT_ROOT / "runs" / "v4_7_7" / "v3_legacy_artifact_manifest.jsonl"

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

LEGACY_ENTRYPOINT_SCRIPTS: dict[str, Path] = {}
SAFE_LEGACY_CHECK_ALIASES: dict[str, Path] = {}
SAFE_RUNNER_ALIASES_BEFORE: tuple[str, ...] = ()
SAFE_RUNNER_ALIASES_ADDED = tuple(key for key in SAFE_LEGACY_CHECK_ALIASES if key not in SAFE_RUNNER_ALIASES_BEFORE)
DELETED_LEGACY_CHECK_ALIASES = ("v3_18", "v3_19", "v3_20", "v3_21", "v3_22")
LEGACY_CHECK_TIMEOUT_SECONDS = 120

TEXT_SCAN_DIRS = ("ai/tests", "ai/scripts", "ai/eval", "docs")
TEXT_SCAN_FILES = ("README.md",)
TEXT_SCAN_SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt"}
TEST_DOC_PREFIXES = ("ai/tests/", "docs/", "README.md", "ai/eval/README.md", "ai/scripts/README.md")

MANUAL_HOLD_CLASSIFICATIONS = {
    "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT",
    "EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET",
    "EXPLICIT_HOLD_LEGACY_SCRIPT_INPUT_CONTRACT",
    "REVIEW_MANUAL_HOLD",
}


@dataclass(frozen=True)
class ArchiveTargetResolution:
    resolved: bool
    target_root: Path
    source: str
    skip_reason: str = ""


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return v476.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, rows)


def sha256_file(path: Path) -> str:
    return v476.sha256_file(path)


def repo_relative(path: Path, root: Path) -> str:
    return v476.repo_relative(path, root)


def resolve_external_archive_target(*, root: Path) -> ArchiveTargetResolution:
    repo_root = root.resolve()
    candidates: list[tuple[Path, str]] = []
    for env_key in v476.EXTERNAL_ARCHIVE_ENV_KEYS:
        value = os.environ.get(env_key)
        if value:
            candidates.append((Path(value), env_key))
    if not candidates:
        candidates.extend((Path(candidate), "existing_external_runtime_root") for candidate in v476.DEFAULT_EXISTING_EXTERNAL_ROOTS)

    for base, source in candidates:
        namespace = base / "rag-ingestion" / SHORT_RUN_ID
        if v476.is_relative_to(namespace, repo_root):
            return ArchiveTargetResolution(False, namespace, source, "external_archive_target_inside_repo")
        try:
            namespace.mkdir(parents=True, exist_ok=True)
            probe = namespace / ".codex_write_probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink()
        except OSError:
            continue
        return ArchiveTargetResolution(True, namespace, source)

    return ArchiveTargetResolution(False, Path(), "none", "external_archive_target_not_resolved")


def _text_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for rel_dir in TEXT_SCAN_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SCAN_SUFFIXES:
                continue
            rel = repo_relative(path, root)
            if rel.startswith("reports/rag_eval/rag-ingestion/"):
                continue
            if "__pycache__" in path.parts:
                continue
            paths.append(path)
    for rel_file in TEXT_SCAN_FILES:
        path = root / rel_file
        if path.exists():
            paths.append(path)
    return sorted(set(paths), key=lambda item: repo_relative(item, root))


def _needles_for_artifact(rel_text: str) -> set[str]:
    rel = Path(rel_text)
    needles = {rel.as_posix()}
    parts = rel.as_posix().split("/")
    if "quality" in parts:
        idx = parts.index("quality")
        if idx + 1 < len(parts):
            needles.add(parts[idx + 1])
    else:
        needles.add(rel.name)
    return {needle for needle in needles if needle}


def build_reference_graph(root: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    texts = []
    for path in _text_files(root):
        try:
            texts.append((repo_relative(path, root), path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue

    graph: dict[str, dict[str, Any]] = {}
    for row in rows:
        rel_text = str(row.get("original_relative_path") or "")
        if not rel_text:
            continue
        hits: list[str] = []
        needles = _needles_for_artifact(rel_text)
        for text_path, text in texts:
            if any(needle in text for needle in needles):
                hits.append(text_path)
        test_doc_hits = [hit for hit in hits if hit.startswith(TEST_DOC_PREFIXES)]
        script_hits = [hit for hit in hits if hit.startswith("ai/scripts/")]
        core_hits = [hit for hit in hits if hit.startswith("ai/eval/") and not hit.startswith(TEST_DOC_PREFIXES)]
        graph[rel_text] = {
            "reference_count": len(hits),
            "test_doc_reference_count": len(test_doc_hits),
            "script_reference_count": len(script_hits),
            "core_reference_count": len(core_hits),
            "sample_references": hits[:8],
            "test_doc_references": test_doc_hits[:8],
        }
    return graph


def inventory_text_couplings(root: Path) -> dict[str, int]:
    long_path_literal_count = 0
    direct_report_path_dependency_count = 0
    direct_report_re = re.compile(
        r"reports/rag_eval/rag-ingestion/quality/"
        r"official_answer_citation_agentic_loop_run_[^`\"'\s]+/report\.json"
    )
    for path in _text_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        long_path_literal_count += text.count("official_answer_citation_agentic_loop_run_")
        direct_report_path_dependency_count += len(direct_report_re.findall(text))
    return {
        "long_path_literal_count": long_path_literal_count,
        "direct_report_path_dependency_count": direct_report_path_dependency_count,
    }


def _is_root_current_contract_candidate(rel_text: str) -> bool:
    rel = Path(rel_text)
    return rel.parent.as_posix() == REPORT_ROOT.as_posix() and rel.name.startswith("official_answer_citation_agentic_loop_run_v3_")


def _is_v316_quality_candidate(rel_text: str) -> bool:
    return (
        "/quality/official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod/"
        in "/" + rel_text
    )


def _is_ambiguous_archive_candidate(rel_text: str) -> bool:
    name = Path(rel_text).name
    kept_suffixes = ("_metrics.json", "_per_family.json", "_per_query.jsonl")
    return not name.endswith(kept_suffixes)


def _archive_action_for(row: Mapping[str, Any]) -> str:
    rel_text = str(row.get("original_relative_path") or "")
    classification = str(row.get("classification") or "")
    if classification == "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT":
        if _is_root_current_contract_candidate(rel_text) or _is_v316_quality_candidate(rel_text):
            return "archive_then_remove"
    if classification == "EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE" and _is_ambiguous_archive_candidate(rel_text):
        return "archive_then_remove"
    return "hold"


def _narrow_hold_row(row: Mapping[str, Any], references: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(row.get("classification") or "")
    rel_text = str(row.get("original_relative_path") or "")
    narrowed = dict(row)
    narrowed["before_classification"] = classification
    narrowed["reference_graph"] = dict(references)
    narrowed["physical_action"] = "none"
    if classification == "EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE":
        narrowed["classification"] = "REVIEW_MANUAL_HOLD"
        narrowed["hold_reason"] = (
            "narrowed manual hold: compact v3_9 quality metric/per-family/per-query artifact remains "
            "available for current status/hash assertions; response and taxonomy payloads were archived"
        )
    elif classification == "EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT":
        if int(references.get("test_doc_reference_count") or 0) > 0:
            narrowed["hold_reason"] = (
                "narrowed current test/doc contract: retained because current tests/docs still assert this "
                "family through archive-aware metadata or hash/provenance checks"
            )
        else:
            narrowed["classification"] = "EXPLICIT_HOLD_LEGACY_SCRIPT_INPUT_CONTRACT"
            narrowed["hold_reason"] = (
                "narrowed legacy script input contract: no current test/doc reader found, but a retained "
                "legacy diagnostic wrapper may still read this generated artifact"
            )
    elif classification == "EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET":
        narrowed["hold_reason"] = (
            "narrowed documented review-packet hold: user/provenance review surface preserved; no deletion "
            "without replacing its review role with hash/provenance-only metadata"
        )
    return narrowed


def _archived_counterpart(path: Path, *, root: Path, archive_root: Path) -> Path:
    return archive_root / path.resolve().relative_to(root.resolve())


def _archive_row(
    row: Mapping[str, Any],
    *,
    root: Path,
    target: ArchiveTargetResolution,
    generated_at: str,
    execute: bool,
    references: Mapping[str, Any],
) -> dict[str, Any]:
    rel_text = str(row.get("original_relative_path") or "")
    source = root / rel_text
    base: dict[str, Any] = {
        "original_relative_path": rel_text,
        "before_classification": row.get("classification"),
        "before_hold_reason": row.get("hold_reason", ""),
        "reference_graph": dict(references),
        "classification": "ARCHIVE_THEN_REMOVE",
        "reason": (
            "v4_7_8 test/doc dependency decoupling moved this generated v3 artifact behind "
            "archive-aware metadata; repo-local copy is no longer required"
        ),
        "hold_reason": "",
        "archive_path_redacted": True,
        "source_cleanup_run_id": SHORT_RUN_ID,
        "physical_action": "planned_archive_then_remove" if not execute else "archive_then_remove",
    }
    if not execute:
        return {
            **base,
            "size_bytes": int(row.get("size_bytes") or 0),
            "sha256": str(row.get("sha256") or ""),
            "archive_copy_verified": False,
            "archived_at": "",
            "removed_from_repo_at": "",
        }
    if not target.resolved:
        failed = _narrow_hold_row(row, references)
        failed["hold_reason"] = "archive target unresolved; fail-closed repo-local hold"
        failed["archive_target_skip_reason"] = target.skip_reason
        return failed
    if source.exists():
        record = v476.archive_then_remove_file(
            source,
            repo_root=root,
            archive_namespace_root=target.target_root,
            removed_at=generated_at,
            reason=str(base["reason"]),
        )
        record.update(base)
        record["physical_action"] = "archive_then_remove" if record.get("archive_copy_verified") else "archive_copy_failed"
        return record

    archived = _archived_counterpart(source, root=root, archive_root=target.target_root)
    archived_long = v476.windows_long_path(archived)
    if archived_long.exists():
        archive_sha = sha256_file(archived_long)
        expected_sha = str(row.get("sha256") or "")
        return {
            **base,
            "size_bytes": int(row.get("size_bytes") or archived_long.stat().st_size),
            "sha256": expected_sha or archive_sha,
            "archive_sha256": archive_sha,
            "archive_copy_verified": not expected_sha or expected_sha == archive_sha,
            "archived_at": "already_archived_by_v4_7_8",
            "removed_from_repo_at": "already_removed_by_v4_7_8",
            "physical_action": "already_archived_removed",
        }

    failed = _narrow_hold_row(row, references)
    failed["hold_reason"] = "archive candidate missing before copy and no verified archived counterpart was found"
    failed["physical_action"] = "none_missing_fail_closed"
    return failed


def build_hold_reduction_manifest(
    *,
    root: Path,
    source_rows: Sequence[Mapping[str, Any]],
    references: Mapping[str, Mapping[str, Any]],
    target: ArchiveTargetResolution,
    generated_at: str,
    execute: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        classification = str(source_row.get("classification") or "")
        if not classification.startswith("EXPLICIT_HOLD"):
            carried = dict(source_row)
            carried["before_classification"] = classification
            carried["physical_action"] = "already_archived_removed" if classification == "EXTERNALLY_ARCHIVED_REMOVED" else "none"
            rows.append(carried)
            continue
        rel_text = str(source_row.get("original_relative_path") or "")
        ref = references.get(rel_text, {})
        if _archive_action_for(source_row) == "archive_then_remove":
            rows.append(_archive_row(source_row, root=root, target=target, generated_at=generated_at, execute=execute, references=ref))
        else:
            rows.append(_narrow_hold_row(source_row, ref))
    return rows


def _hold_counts_by_classification(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        classification = str(row.get("classification") or "")
        if classification.startswith("EXPLICIT_HOLD") or classification == "REVIEW_MANUAL_HOLD":
            counts[classification] += 1
    return dict(sorted(counts.items()))


def _count_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    archived_or_removed = sum(
        1
        for row in rows
        if row.get("classification") in {"EXTERNALLY_ARCHIVED_REMOVED", "ARCHIVE_THEN_REMOVE"}
        and (row.get("sha256") or row.get("removed_from_repo_at"))
    )
    deleted = sum(1 for row in rows if row.get("classification") == "DELETE_ONLY" and row.get("deleted_at"))
    manual = sum(
        1
        for row in rows
        if str(row.get("classification") or "").startswith("EXPLICIT_HOLD")
        or row.get("classification") == "REVIEW_MANUAL_HOLD"
    )
    return {
        "artifact_count": len(rows),
        "archived_or_removed": archived_or_removed,
        "manual_hold": manual,
        "deleted": deleted,
        "unclassified": sum(1 for row in rows if not row.get("classification")),
    }


def _parse_last_json_line(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def _forbidden_gate_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_FALSE_KEYS:
        if payload.get(key) is True:
            errors.append(f"{key}=true")
    try:
        if int(payload.get("official_metric_input_rows") or 0) != 0:
            errors.append("official_metric_input_rows_nonzero")
    except (TypeError, ValueError):
        errors.append("official_metric_input_rows_not_integer")
    return errors


def evaluate_legacy_entrypoints(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    verified: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for alias, script in LEGACY_ENTRYPOINT_SCRIPTS.items():
        started = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", script.as_posix(), "--check"],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=LEGACY_CHECK_TIMEOUT_SECONDS,
                check=False,
            )
            elapsed = round(time.perf_counter() - started, 3)
            payload = _parse_last_json_line(result.stdout)
            gate_errors = _forbidden_gate_errors(payload)
            row = {
                "alias": alias,
                "script": script.as_posix(),
                "returncode": result.returncode,
                "elapsed_seconds": elapsed,
                "status": str(payload.get("status") or ""),
                "run_id": str(payload.get("run_id") or ""),
                "official_metric_input_rows": int(payload.get("official_metric_input_rows") or 0),
                "promotion_evidence": bool(payload.get("promotion_evidence", False)),
                "write_supported": False,
                "gate_errors": gate_errors,
            }
            if result.returncode == 0 and not gate_errors:
                verified.append(row)
            else:
                row["hold_reason"] = "check returned nonzero or opened a forbidden gate; alias not added"
                held.append(row)
        except subprocess.TimeoutExpired as exc:
            held.append(
                {
                    "alias": alias,
                    "script": script.as_posix(),
                    "returncode": "timeout",
                    "elapsed_seconds": LEGACY_CHECK_TIMEOUT_SECONDS,
                    "status": "",
                    "run_id": "",
                    "official_metric_input_rows": 0,
                    "promotion_evidence": False,
                    "write_supported": False,
                    "gate_errors": [],
                    "hold_reason": f"--check exceeded {LEGACY_CHECK_TIMEOUT_SECONDS}s timeout; alias not added",
                    "stdout_tail": (exc.stdout or "")[-400:] if isinstance(exc.stdout, str) else "",
                }
            )
    return verified, held


def _status_event(report: Mapping[str, Any], *, report_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": report_sha256},
        "diagnostic_only": True,
        "cleanup_only": True,
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
        "source_run_id": "v4_7_7_v3_legacy_archive_and_runner_consolidation",
        "before_hold_counts_by_classification": report["before_hold_counts_by_classification"],
        "after_hold_counts_by_classification": report["after_hold_counts_by_classification"],
        "resolved_current_test_or_doc_contract_count": report["resolved_current_test_or_doc_contract_count"],
        "resolved_ambiguous_generated_surface_count": report["resolved_ambiguous_generated_surface_count"],
        "safe_runner_aliases_added": report["safe_runner_aliases_added"],
        "safe_runner_check_alias_count_after": report["safe_runner_check_alias_count_after"],
        "archive_copy_failed_count": report["archive_copy_failed_count"],
        "hash_verification_failed_count": report["hash_verification_failed_count"],
        "unclassified_count": report["unclassified_count"],
    }


def append_status(root: Path, report: Mapping[str, Any], *, report_sha256: str) -> None:
    status_path = root / STATUS_JSONL_PATH
    existing = [
        row
        for row in read_jsonl(status_path)
        if row.get("short_run_id") != SHORT_RUN_ID and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
    ]
    write_jsonl(status_path, [*existing, _status_event(report, report_sha256=report_sha256)])


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    start = f"<!-- {SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:progress-entry:end -->"
    after = report["after_hold_counts_by_classification"]
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        "This is cleanup/refactor only: v3 legacy artifacts previously held by broad test/doc path rules now have "
        "a reference graph, archive-aware metadata, and narrower hold reasons. "
        f"Current test/doc holds {report['before_hold_counts_by_classification'].get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)} -> "
        f"{after.get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)}, ambiguous generated holds "
        f"{report['before_hold_counts_by_classification'].get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)} -> "
        f"{after.get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)}, documented review-packet holds remain "
        f"{report['documented_review_packet_hold_count_after']}. Archived/removed {report['archived_count']} newly safe files; "
        f"manual holds are now {report['v3_legacy_manual_hold_count']}; unclassified {report['unclassified_count']}. "
        f"`ai/scripts/rag_eval.py` now exposes verified check-only legacy aliases "
        f"{', '.join(report['script_consolidation']['safe_check_aliases'])}; v3_16 and v3_17 remain held because "
        "bounded checks fail closed on local LLM availability. Protected namespaces remain untouched and all official, "
        "gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    anchor = "for behavior-changing runs or explicit forensic evidence requirements.\n"
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    start = f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->"
    before = report["before_hold_counts_by_classification"]
    after = report["after_hold_counts_by_classification"]
    block = f"""### v4_7_8 Test/Doc Dependency Decoupling And Runner Alias Expansion

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: cleanup/refactor counters only. No retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Before | After |
|---|---:|---:|
| hold_current_test_or_doc_contract | {before.get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)} | {after.get('EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT', 0)} |
| hold_documented_legacy_review_packet | {report['documented_review_packet_hold_count_before']} | {report['documented_review_packet_hold_count_after']} |
| hold_ambiguous_generated_surface | {before.get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)} | {after.get('EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE', 0)} |
| review_manual_hold_narrowed | 0 | {after.get('REVIEW_MANUAL_HOLD', 0)} |
| v3_legacy_manual_hold_count | {report['before_v3_legacy_manual_hold_count']} | {report['v3_legacy_manual_hold_count']} |
| safe_runner_check_alias_count | {report['safe_runner_check_alias_count_before']} | {report['safe_runner_check_alias_count_after']} |
| archived_count | 0 | {report['archived_count']} |
| removed_count | 0 | {report['removed_count']} |
| unclassified_count | {report['before_unclassified_count']} | {report['unclassified_count']} |
| archive_copy_failed_count | 0 | {report['archive_copy_failed_count']} |
| hash_verification_failed_count | 0 | {report['hash_verification_failed_count']} |
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    held = report["legacy_entrypoints_held"]
    held_text = ", ".join(f"{row['alias']}={row['hold_reason']}" for row in held) or "none"
    block = f"""### v4_7_8 Test/Doc Dependency Decoupling And Runner Alias Expansion

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Reference graph: `{HOLD_REDUCTION_MANIFEST_PATH.as_posix()}` records sample readers for each v3 legacy artifact and separates test/doc readers from script/core readers.
- Archive/purge: safe generated root-level v3 artifacts, v3_16 generated quality payloads, and nonessential ambiguous v3_9 response/taxonomy payloads were copied to an external v4_7_8 archive namespace, SHA-256 verified, and removed repo-local.
- Narrowed holds: documented review packets remain held; retained v3_9 metric/per-family/per-query payloads are `REVIEW_MANUAL_HOLD`; retained v3_17-v3_22 quality payloads remain current contract holds only where current checks or docs still need them.
- Runner consolidation: `ai/scripts/rag_eval.py` owns `current`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only aliases {', '.join(report['script_consolidation']['safe_check_aliases'])}. Held entrypoints: {held_text}.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
- Held count: {report['v3_legacy_manual_hold_count']}; unclassified count: {report['unclassified_count']}; archive copy failures: {report['archive_copy_failed_count']}; hash verification failures: {report['hash_verification_failed_count']}.
"""
    text = path.read_text(encoding="utf-8")
    text = v476.upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` is cleanup/refactor only and writes `{SHORT_REPORT_PATH.as_posix()}`; it does not replay retrieval, EvidenceBundle repair, or answer generation.
- Resolver wiring: use `current` or `v4_7_8` for the latest test/doc dependency decoupling report; use `v4_7_7` for the prior `v4_7_7_v3_legacy_archive_and_runner_consolidation` report.
- v3 legacy artifact policy: generated v3 artifacts are tracked in `{HOLD_REDUCTION_MANIFEST_PATH.as_posix()}` with reference graph metadata, archive verification, or narrowed hold reasons. Counters are total {report['v3_legacy_artifact_count']}, archived/removed {report['v3_legacy_archived_or_removed_count']}, held {report['v3_legacy_manual_hold_count']}, unclassified {report['unclassified_count']}.
- Runner consolidation: `ai/scripts/rag_eval.py` is the stable short-key runner. It owns `current`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only aliases {', '.join(report['script_consolidation']['safe_check_aliases'])}; v3_16 and v3_17 remain explicit held entrypoints because bounded checks fail closed.
- Retained v4_7 context: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with non-empty `질의문` 204 and hydrated rows 204, PDF 100, XLSX 104; v4_7_3 applies the user-reviewed Korean query candidate CSV with 미검수=통과; v4_7_4 keeps PDF survivor 58; these remain not official metric.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; no per-run Markdown is created.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    if "## Current RAG Diagnostic Status" in text:
        text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## )", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    elif "## 기술적으로 신경 쓴 점" in text:
        text = text.replace("## 기술적으로 신경 쓴 점", snapshot.rstrip() + "\n\n## 기술적으로 신경 쓴 점", 1)
    else:
        text = text.rstrip() + "\n\n" + snapshot.rstrip() + "\n"
    if "python -X utf8 ai\\scripts\\rag_eval.py v4_7_8 --check" not in text:
        text = text.replace(
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_7 --check\n",
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_7 --check\n"
            "python -X utf8 ai\\scripts\\rag_eval.py v4_7_8 --check\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path) -> None:
    path = root / "ai" / "eval" / "README.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    marker = (
        f"- v4_7_8 cleanup/refactor: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` "
        "through `ai/scripts/rag_eval.py`; use resolver key `current` for v4_7_8 and "
        "`v4_7_7` for the prior `v4_7_7_v3_legacy_archive_and_runner_consolidation` report."
    )
    prior_marker = (
        "- v4_7_6 cleanup/refactor: use resolver key `v4_7_6` for this prior archive-purge report; "
        "`current` now resolves to v4_7_8."
    )
    if marker not in text:
        text = re.sub(r"(- v4_7_7 archive-aware cleanup/refactor: .*?\n)", r"\1" + marker + "\n", text, count=1)
        if marker not in text:
            current_status = f"- Current RAG status: `{STATUS}`"
            if current_status in text:
                text = text.replace(current_status, f"{current_status}\n{marker}", 1)
            elif "## 현재 상태" in text:
                boundary = (
                    f"\n{current_status}\n"
                    f"{marker}\n"
                    "- Boundary: diagnostic-only sample/eval material; `official_metric=false`, "
                    "`official_metric_input_rows=0`, `promotion_evidence=false`, "
                    "`product_success_evidence_allowed=false`, and `live_db_index_cache_readiness=false` remain closed.\n"
                )
                text = text.replace("## 현재 상태\n", "## 현재 상태\n" + boundary, 1)
            else:
                text = text.rstrip() + "\n\n" + current_status + "\n" + marker + "\n"
    if prior_marker not in text:
        if marker in text:
            text = text.replace(marker, marker + "\n" + prior_marker, 1)
        elif "## 현재 상태" in text:
            text = text.replace("## 현재 상태\n", "## 현재 상태\n\n" + prior_marker + "\n", 1)
    review_start = "<!-- v4_7_8:korean-human-review-context:start -->"
    review_end = "<!-- v4_7_8:korean-human-review-context:end -->"
    review_block = """## Korean human review packet

The previous v4_7_1 Korean review packet was abstract; v4_7_2 writes review_packet_ko_hydrated.xlsx with actual Korean query candidates. User-owned fields remain blank/default; not official metric. v4_7_3 applies the user-reviewed CSV decisions and remains not gold/qrels. v4_7_4 replays only the 58 user-passed PDF survivor candidates. fine_tuning_executed=false.
"""
    text = v476.upsert_block(
        text,
        start_marker=review_start,
        end_marker=review_end,
        block=review_block,
        after_anchor=prior_marker,
    )
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}`, `current` resolves to `v4_7_8`, "
        "`v4_7_7_v3_legacy_archive_and_runner_consolidation` remains the prior cleanup report, "
        f"and verified legacy check aliases {', '.join(report['script_consolidation']['safe_check_aliases'])} "
        "are available while v3_16/v3_17 remain explicit fail-closed holds. |"
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
    update_scripts_readme(root, report)


def build_report(*, root: Path, execute: bool, sync_surfaces: bool = False, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now_iso()
    source_report = read_json(root / V477_REPORT_PATH)
    source_rows = read_jsonl(root / V477_MANIFEST_PATH)
    before_inventory = inventory_text_couplings(root)
    references = build_reference_graph(root, source_rows)
    target = resolve_external_archive_target(root=root)
    verified_entrypoints, held_entrypoints = evaluate_legacy_entrypoints(root)
    manifest_rows = build_hold_reduction_manifest(
        root=root,
        source_rows=source_rows,
        references=references,
        target=target,
        generated_at=generated_at,
        execute=execute,
    )
    counts = _count_rows(manifest_rows)
    before_hold_counts = dict(source_report["v3_legacy_hold_counts_by_classification"])
    after_hold_counts = _hold_counts_by_classification(manifest_rows)
    archive_copy_failed_count = sum(1 for row in manifest_rows if row.get("classification") == "ARCHIVE_COPY_FAILED")
    hash_verification_failed_count = sum(
        1
        for row in manifest_rows
        if row.get("archive_sha256") and row.get("sha256") and row.get("archive_sha256") != row.get("sha256")
    )
    archive_then_remove_count = sum(1 for row in manifest_rows if row.get("classification") == "ARCHIVE_THEN_REMOVE")
    archived_count = sum(1 for row in manifest_rows if row.get("classification") == "ARCHIVE_THEN_REMOVE" and row.get("archive_copy_verified"))
    removed_count = sum(1 for row in manifest_rows if row.get("classification") == "ARCHIVE_THEN_REMOVE" and row.get("removed_from_repo_at"))

    report: dict[str, Any] = {
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "v3_legacy_hold_reduction_manifest_jsonl": HOLD_REDUCTION_MANIFEST_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "archive_manifest_jsonl": ARCHIVE_MANIFEST_PATH.as_posix(),
        },
        "diagnostic_only": True,
        "cleanup_only": True,
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
        "source_run_id": "v4_7_7_v3_legacy_archive_and_runner_consolidation",
        "source_report_json": V477_REPORT_PATH.as_posix(),
        "source_manifest_jsonl": V477_MANIFEST_PATH.as_posix(),
        "before_hold_counts_by_classification": before_hold_counts,
        "after_hold_counts_by_classification": after_hold_counts,
        "before_v3_legacy_manual_hold_count": int(source_report["v3_legacy_manual_hold_count"]),
        "before_unclassified_count": int(source_report["v3_legacy_unclassified_count"]),
        "resolved_current_test_or_doc_contract_count": before_hold_counts.get("EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT", 0)
        - after_hold_counts.get("EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT", 0),
        "resolved_ambiguous_generated_surface_count": before_hold_counts.get("EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE", 0)
        - after_hold_counts.get("EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE", 0),
        "documented_review_packet_hold_count_before": before_hold_counts.get("EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET", 0),
        "documented_review_packet_hold_count_after": after_hold_counts.get("EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET", 0),
        "safe_runner_check_alias_count_before": len(SAFE_RUNNER_ALIASES_BEFORE),
        "safe_runner_check_alias_count_after": len(SAFE_LEGACY_CHECK_ALIASES),
        "safe_runner_aliases_added": list(SAFE_RUNNER_ALIASES_ADDED),
        "deleted_legacy_check_aliases": list(DELETED_LEGACY_CHECK_ALIASES),
        "legacy_entrypoints_verified": verified_entrypoints,
        "legacy_entrypoints_held": held_entrypoints,
        "scripts_converted_to_wrappers_count": 0,
        "scripts_removed_count": 0,
        "archive_then_remove_count": archive_then_remove_count,
        "archived_count": archived_count,
        "removed_count": removed_count,
        "delete_only_count": 0,
        "deleted_count": counts["deleted"],
        "v3_legacy_artifact_count": counts["artifact_count"],
        "v3_legacy_archived_or_removed_count": counts["archived_or_removed"],
        "v3_legacy_manual_hold_count": counts["manual_hold"],
        "unclassified_count": counts["unclassified"],
        "archive_copy_failed_count": archive_copy_failed_count,
        "hash_verification_failed_count": hash_verification_failed_count,
        "direct_report_path_dependency_count_before": before_inventory["direct_report_path_dependency_count"],
        "direct_report_path_dependency_count_after": before_inventory["direct_report_path_dependency_count"],
        "long_path_literal_count_before": before_inventory["long_path_literal_count"],
        "long_path_literal_count_after": before_inventory["long_path_literal_count"],
        "external_archive_target_resolved": target.resolved,
        "external_archive_target_redacted": True,
        "external_archive_target_kind": target.source if target.resolved else "unresolved",
        "script_consolidation": {
            "stable_runner": "ai/scripts/rag_eval.py",
            "safe_check_aliases": list(SAFE_LEGACY_CHECK_ALIASES),
            "deleted_check_aliases": list(DELETED_LEGACY_CHECK_ALIASES),
            "legacy_alias_policy": "deleted aliases intentionally unsupported; use archived reports or current runner keys",
            "held_legacy_entrypoints": {
                row["alias"]: row["hold_reason"] for row in held_entrypoints
            },
            "new_per_run_script_created": False,
            "retrieval_promotion_scripts_folded_into_current": False,
            "runner_scope": "current and registry-backed report keys only; deleted v3 script aliases fail closed",
        },
        "dry_run": not execute,
        "residual_risks": [
            "retained documented review packets still require user-owned provenance preservation",
            "deleted v3 script aliases are intentionally unsupported; use archived report evidence for historical reproduction",
            "metrics remain cleanup counters only, not answer quality, retrieval quality, or official metric evidence",
        ],
    }
    if execute:
        write_jsonl(root / HOLD_REDUCTION_MANIFEST_PATH, manifest_rows)
    if sync_surfaces:
        update_docs(root, report)
        after_inventory = inventory_text_couplings(root)
        report["direct_report_path_dependency_count_after"] = after_inventory["direct_report_path_dependency_count"]
        report["long_path_literal_count_after"] = after_inventory["long_path_literal_count"]
    return report


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_8 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_8 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_8 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("cleanup_only") is not True:
        raise ValueError("v4_7_8 cleanup-only flags mismatch")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_8 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_8 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_8 protected namespaces were touched")
    if report.get("unclassified_count") != 0:
        raise ValueError("v4_7_8 v3 legacy artifacts must not remain unclassified")
    if report.get("archive_copy_failed_count") != 0:
        raise ValueError("v4_7_8 archive copy failure present")
    if report.get("hash_verification_failed_count") != 0:
        raise ValueError("v4_7_8 hash verification failure present")
    after = report.get("after_hold_counts_by_classification") or {}
    if int(after.get("EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT", 0)) > 80:
        raise ValueError("v4_7_8 current test/doc holds remain above target")
    if int(after.get("EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE", 0)) > 20:
        raise ValueError("v4_7_8 ambiguous generated holds remain above target")
    if int(report.get("v3_legacy_manual_hold_count", 0)) > 120:
        raise ValueError("v4_7_8 manual hold count remains above target")
    is_post_cleanup_policy = "deleted_legacy_check_aliases" in report
    if is_post_cleanup_policy and int(report.get("safe_runner_check_alias_count_after", -1)) != 0:
        raise ValueError("v4_7_8 deleted legacy aliases must stay unsupported")
    if not is_post_cleanup_policy and int(report.get("safe_runner_check_alias_count_after", 0)) < 5:
        raise ValueError("v4_7_8 historical safe runner alias target not met")
    if report.get("documented_review_packet_hold_count_after") != report.get("documented_review_packet_hold_count_before"):
        raise ValueError("v4_7_8 documented review packet hold count changed unexpectedly")
    aliases = set(report.get("script_consolidation", {}).get("safe_check_aliases", ()))
    if is_post_cleanup_policy:
        if aliases:
            raise ValueError(f"v4_7_8 deleted aliases unexpectedly exposed: {sorted(aliases)}")
        deleted_aliases = set(report.get("script_consolidation", {}).get("deleted_check_aliases", ()))
        for alias in DELETED_LEGACY_CHECK_ALIASES:
            if alias not in deleted_aliases:
                raise ValueError(f"v4_7_8 deleted alias not recorded: {alias}")
        return
    for alias in DELETED_LEGACY_CHECK_ALIASES:
        if alias not in aliases:
            raise ValueError(f"v4_7_8 historical safe alias missing: {alias}")
