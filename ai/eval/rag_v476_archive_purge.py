from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ai.eval.report_paths import LEGACY_RAG_INGESTION_REPORT_ROOT, REPO_ROOT
from ai.eval import rag_eval_registry as registry


LOGICAL_RUN_KEY = "v4_7_6"
SHORT_RUN_ID = "v4_7_6_eval_artifact_archive_purge"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_6_"
    "eval_artifact_external_archive_and_purge_nonprod"
)
STATUS = "V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY"

REPORT_ROOT = LEGACY_RAG_INGESTION_REPORT_ROOT.relative_to(REPO_ROOT)
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
CLEANUP_MANIFEST_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "cleanup_manifest.jsonl"
ARCHIVE_MANIFEST_PATH = REPORT_ROOT / "archive_manifest.jsonl"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"

PROTECTED_PREFIXES = (
    Path("ai/eval/eval_queries"),
    Path("ai/eval/source_registry"),
    Path("ai/eval/indexes"),
    Path("ai/eval/silver"),
)
CURRENT_LINEAGE_KEYS = ("v4_7_preofficial", "v4_7_2", "v4_7_3", "v4_7_4", "v4_7_5", "v4_7_6")
CURRENT_LINEAGE_SHORT_REPORTS = tuple(
    REPORT_ROOT / "runs" / key / "report.json" for key in CURRENT_LINEAGE_KEYS
)
CURRENT_MINIMAL_PATHS = {
    STATUS_JSONL_PATH,
    ARCHIVE_MANIFEST_PATH,
    REPORT_ROOT / "current.json",
    CLEANUP_MANIFEST_PATH,
    *CURRENT_LINEAGE_SHORT_REPORTS,
}
ARCHIVE_ROOT_LEVEL_PREFIX_RE = re.compile(
    r"^official_answer_citation_agentic_loop_run_v3_(?:9(?:_|$)|1[0-5](?:_|$)).*\.(?:json|jsonl|csv|xlsx|md)$"
)
DIRECT_REPORT_PATH_RE = re.compile(
    r"reports/rag_eval/rag-ingestion/quality/"
    r"official_answer_citation_agentic_loop_run_[^`\"'\s]+/report\.json"
)
TEXT_SCAN_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json"}
TEXT_SCAN_DIRS = ("ai/scripts", "ai/tests", "ai/eval", "docs")
EXTERNAL_ARCHIVE_ENV_KEYS = ("RAG_EVAL_EXTERNAL_ARCHIVE_ROOT", "EXTERNAL_RUNTIME_ARTIFACTS_ROOT")
DEFAULT_EXISTING_EXTERNAL_ROOTS = (
    Path("D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline"),
)


@dataclass(frozen=True)
class ArchiveTargetResolution:
    resolved: bool
    target_root: Path
    redacted: bool
    skip_reason: str
    source: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def normalized_repo_path(path: Path, root: Path) -> Path:
    try:
        return Path(repo_relative(path, root))
    except ValueError:
        return Path(path.as_posix())


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def windows_long_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    path_text = str(path.resolve())
    if path_text.startswith("\\\\?\\"):
        return path
    return Path("\\\\?\\" + path_text)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def resolve_external_archive_target(
    *,
    root: Path,
    env: Mapping[str, str] | None = None,
    existing_roots: Iterable[Path] | None = None,
) -> ArchiveTargetResolution:
    env = os.environ if env is None else env
    repo_root = root.resolve()
    candidate_bases: list[tuple[Path, str]] = []
    for env_key in EXTERNAL_ARCHIVE_ENV_KEYS:
        value = env.get(env_key)
        if value:
            candidate_bases.append((Path(value), env_key))
    if not candidate_bases:
        roots = DEFAULT_EXISTING_EXTERNAL_ROOTS if existing_roots is None else tuple(existing_roots)
        candidate_bases.extend((Path(candidate), "existing_external_runtime_root") for candidate in roots)

    for base, source in candidate_bases:
        namespace_root = base / "rag-ingestion" / SHORT_RUN_ID
        if is_relative_to(namespace_root, repo_root):
            return ArchiveTargetResolution(
                resolved=False,
                target_root=namespace_root,
                redacted=True,
                skip_reason="external_archive_target_inside_repo",
                source=source,
            )
        try:
            namespace_root.mkdir(parents=True, exist_ok=True)
            probe = namespace_root / ".codex_write_probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink()
        except OSError:
            continue
        return ArchiveTargetResolution(
            resolved=True,
            target_root=namespace_root,
            redacted=True,
            skip_reason="",
            source=source,
        )

    return ArchiveTargetResolution(
        resolved=False,
        target_root=Path(),
        redacted=True,
        skip_reason="external_archive_target_not_resolved",
        source="none",
    )


def archive_then_remove_file(
    source: Path,
    *,
    repo_root: Path,
    archive_namespace_root: Path,
    removed_at: str,
    reason: str = "legacy generated diagnostic artifact no longer needed repo-local",
) -> dict[str, Any]:
    source = source.resolve()
    repo_root = repo_root.resolve()
    relative = source.relative_to(repo_root)
    archive_path = archive_namespace_root / relative
    windows_long_path(archive_path.parent).mkdir(parents=True, exist_ok=True)
    source_sha256 = sha256_file(source)
    size_bytes = source.stat().st_size
    shutil.copy2(windows_long_path(source), windows_long_path(archive_path))
    archive_sha256 = sha256_file(windows_long_path(archive_path))
    verified = source_sha256 == archive_sha256
    record: dict[str, Any] = {
        "original_relative_path": relative.as_posix(),
        "size_bytes": size_bytes,
        "sha256": source_sha256,
        "classification": "ARCHIVE_THEN_REMOVE",
        "reason": reason,
        "archive_relative_path": relative.as_posix(),
        "archive_sha256": archive_sha256,
        "archive_copy_verified": verified,
        "archived_at": removed_at if verified else "",
        "removed_from_repo_at": "",
        "archive_path_redacted": True,
    }
    if not verified:
        record["classification"] = "ARCHIVE_COPY_FAILED"
        record["reason"] = "archive sha256 verification failed; repo-local source preserved"
        return record
    windows_long_path(source).unlink()
    record["removed_from_repo_at"] = removed_at
    return record


def classify_path(path: Path, *, root: Path, ignored: bool = True) -> str:
    rel = normalized_repo_path(path, root)
    if any(rel == protected or rel.is_relative_to(protected) for protected in PROTECTED_PREFIXES):
        return "KEEP_PROTECTED"
    if path.name in {"__pycache__", ".pytest_cache"} or path.suffix in {".pyc", ".pyo"}:
        return "DELETE_ONLY"
    if rel in CURRENT_MINIMAL_PATHS:
        return "KEEP_CURRENT_MINIMAL"
    if rel.is_relative_to(REPORT_ROOT / "runs"):
        return "KEEP_CURRENT_MINIMAL" if rel in CURRENT_MINIMAL_PATHS else "REVIEW_MANUAL_HOLD"
    if rel.is_relative_to(REPORT_ROOT / "quality"):
        text = rel.as_posix()
        if any(key in text for key in ("v4_7_preofficial", "v4_7_2", "v4_7_3", "v4_7_4", "v4_7_5")):
            return "KEEP_CURRENT_MINIMAL"
        return "REVIEW_MANUAL_HOLD"
    if not ignored and rel.as_posix().startswith("reports/rag_eval/rag-ingestion/"):
        return "REVIEW_MANUAL_HOLD"
    if ignored and rel.parent == REPORT_ROOT and ARCHIVE_ROOT_LEVEL_PREFIX_RE.match(rel.name):
        return "ARCHIVE_THEN_REMOVE"
    if ignored and rel.as_posix().startswith("reports/rag_eval/rag-ingestion/perf/"):
        return "ARCHIVE_THEN_REMOVE"
    if rel.as_posix().startswith("ai/eval/"):
        return "KEEP_PROTECTED" if path.suffix in {".py", ".md"} else "REVIEW_MANUAL_HOLD"
    return "REVIEW_MANUAL_HOLD"


def count_report_tree(root: Path) -> dict[str, int]:
    report_root = root / REPORT_ROOT
    files = [path for path in report_root.rglob("*") if path.is_file()] if report_root.exists() else []
    dirs = [path for path in report_root.rglob("*") if path.is_dir()] if report_root.exists() else []
    return {
        "file_count": len(files),
        "dir_count": len(dirs),
        "bytes": sum(path.stat().st_size for path in files),
    }


def inventory_paths(root: Path) -> tuple[list[Path], list[Path]]:
    eval_root = root / "ai" / "eval"
    files = sorted((path for path in eval_root.rglob("*") if path.is_file()), key=lambda path: repo_relative(path, root))
    dirs = sorted((path for path in eval_root.rglob("*") if path.is_dir()), key=lambda path: repo_relative(path, root))
    return files, dirs


def count_classifications(root: Path) -> dict[str, int]:
    counts = {
        "KEEP_PROTECTED": 0,
        "KEEP_CURRENT_MINIMAL": 0,
        "ARCHIVE_THEN_REMOVE": 0,
        "DELETE_ONLY": 0,
        "REVIEW_MANUAL_HOLD": 0,
    }
    files, dirs = inventory_paths(root)
    for path in [*files, *dirs]:
        classification = classify_path(path, root=root, ignored=True)
        counts[classification] = counts.get(classification, 0) + 1
    return counts


def scan_text_couplings(root: Path) -> dict[str, int]:
    scan_files = [root / "README.md"]
    for rel_dir in TEXT_SCAN_DIRS:
        base = root / rel_dir
        if base.exists():
            scan_files.extend(path for path in base.rglob("*") if path.is_file() and path.suffix in TEXT_SCAN_SUFFIXES)
    long_path_literal_count = 0
    direct_report_path_dependency_count = 0
    for path in sorted(set(scan_files)):
        rel = normalized_repo_path(path, root).as_posix()
        if rel.startswith("reports/rag_eval/rag-ingestion/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        long_path_literal_count += text.count("official_answer_citation_agentic_loop_run_")
        direct_report_path_dependency_count += len(DIRECT_REPORT_PATH_RE.findall(text))
    return {
        "long_path_literal_count": long_path_literal_count,
        "direct_report_path_dependency_count": direct_report_path_dependency_count,
    }


def migrate_current_lineage_reports(root: Path, *, migrated_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in ("v4_7_preofficial", "v4_7_2", "v4_7_3", "v4_7_4"):
        source = registry.legacy_report_path(key, root=root)
        if source is None or not source.exists():
            records.append(
                {
                    "original_relative_path": "",
                    "classification": "REVIEW_MANUAL_HOLD",
                    "reason": f"{key} legacy report missing; short lineage copy skipped",
                    "migrated_at": "",
                }
            )
            continue
        target = registry.resolve_run(key, root=root).report_path
        source_sha = sha256_file(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256_file(target) != source_sha:
            shutil.copy2(source, target)
        target_sha = sha256_file(target)
        records.append(
            {
                "original_relative_path": repo_relative(source, root),
                "replacement_path": repo_relative(target, root),
                "size_bytes": source.stat().st_size,
                "sha256": source_sha,
                "replacement_sha256": target_sha,
                "classification": "KEEP_CURRENT_MINIMAL",
                "reason": "current lineage report copied to short resolver path with bytes preserved",
                "migrated_at": migrated_at if source_sha == target_sha else "",
                "hash_verified": source_sha == target_sha,
            }
        )
    return records


def archive_candidates(root: Path) -> list[Path]:
    report_root = root / REPORT_ROOT
    if not report_root.exists():
        return []
    candidates: list[Path] = []
    for path in sorted(report_root.iterdir(), key=lambda item: item.name):
        if path.is_file() and classify_path(path, root=root, ignored=True) == "ARCHIVE_THEN_REMOVE":
            candidates.append(path)
    perf_dir = report_root / "perf"
    if perf_dir.exists():
        candidates.extend(sorted(path for path in perf_dir.rglob("*") if path.is_file()))
    return candidates


def delete_only_candidates(root: Path) -> list[Path]:
    eval_root = root / "ai" / "eval"
    if not eval_root.exists():
        return []
    candidates: list[Path] = []
    for path in eval_root.rglob("*"):
        if any(is_relative_to(path, root / protected) for protected in PROTECTED_PREFIXES):
            continue
        if path.name in {"__pycache__", ".pytest_cache"}:
            candidates.append(path)
        elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
            candidates.append(path)
    return sorted(candidates, key=lambda item: (item.is_file(), len(item.parts)), reverse=True)


def remove_delete_only(path: Path, *, root: Path, deleted_at: str) -> dict[str, Any]:
    rel = repo_relative(path, root)
    record: dict[str, Any] = {
        "original_relative_path": rel,
        "classification": "DELETE_ONLY",
        "reason": "transient Python or pytest cache with no durable evidence role",
        "deleted_at": "",
        "size_bytes": 0,
        "sha256": "",
    }
    if path.is_file():
        record["size_bytes"] = path.stat().st_size
        record["sha256"] = sha256_file(path)
        path.unlink()
        record["deleted_at"] = deleted_at
    elif path.is_dir():
        file_sizes = [child.stat().st_size for child in path.rglob("*") if child.is_file()]
        record["size_bytes"] = sum(file_sizes)
        shutil.rmtree(path)
        record["deleted_at"] = deleted_at
    return record


def remove_empty_report_dirs(root: Path) -> int:
    report_root = root / REPORT_ROOT
    removed = 0
    if not report_root.exists():
        return removed
    for path in sorted((p for p in report_root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if path == report_root:
            continue
        try:
            path.rmdir()
        except OSError:
            continue
        removed += 1
    return removed


def run_cleanup(root: Path, *, execute: bool, generated_at: str) -> tuple[list[dict[str, Any]], ArchiveTargetResolution]:
    target = resolve_external_archive_target(root=root)
    records: list[dict[str, Any]] = []
    if execute:
        records.extend(migrate_current_lineage_reports(root, migrated_at=generated_at))
    else:
        for key in ("v4_7_preofficial", "v4_7_2", "v4_7_3", "v4_7_4"):
            source = registry.legacy_report_path(key, root=root)
            if source is not None and source.exists():
                records.append(
                    {
                        "original_relative_path": repo_relative(source, root),
                        "replacement_path": registry.resolve_run(key, root=root).report_path.relative_to(root).as_posix(),
                        "size_bytes": source.stat().st_size,
                        "sha256": sha256_file(source),
                        "classification": "KEEP_CURRENT_MINIMAL",
                        "reason": "dry-run current lineage short-path migration candidate",
                        "migrated_at": "",
                        "hash_verified": False,
                    }
                )
    for source in archive_candidates(root):
        if not target.resolved:
            records.append(
                {
                    "original_relative_path": repo_relative(source, root),
                    "size_bytes": source.stat().st_size,
                    "sha256": sha256_file(source),
                    "classification": "ARCHIVE_THEN_REMOVE",
                    "reason": "external archive target unresolved; repo-local source preserved",
                    "archive_relative_path": "",
                    "archived_at": "",
                    "removed_from_repo_at": "",
                    "archive_copy_verified": False,
                    "archive_path_redacted": True,
                }
            )
            continue
        if execute:
            records.append(
                archive_then_remove_file(
                    source,
                    repo_root=root,
                    archive_namespace_root=target.target_root,
                    removed_at=generated_at,
                )
            )
        else:
            records.append(
                {
                    "original_relative_path": repo_relative(source, root),
                    "size_bytes": source.stat().st_size,
                    "sha256": sha256_file(source),
                    "classification": "ARCHIVE_THEN_REMOVE",
                    "reason": "dry-run candidate; no repo-local source removed",
                    "archive_relative_path": repo_relative(source, root),
                    "archived_at": "",
                    "removed_from_repo_at": "",
                    "archive_copy_verified": False,
                    "archive_path_redacted": True,
                }
            )
    for path in delete_only_candidates(root):
        if not path.exists():
            continue
        if execute:
            records.append(remove_delete_only(path, root=root, deleted_at=generated_at))
        else:
            records.append(
                {
                    "original_relative_path": repo_relative(path, root),
                    "classification": "DELETE_ONLY",
                    "reason": "dry-run transient cache candidate",
                    "deleted_at": "",
                    "size_bytes": path.stat().st_size if path.is_file() else 0,
                    "sha256": sha256_file(path) if path.is_file() else "",
                }
            )
    if execute:
        remove_empty_report_dirs(root)
    return records, target


def append_archive_manifest(root: Path, records: list[dict[str, Any]]) -> None:
    manifest_path = root / ARCHIVE_MANIFEST_PATH
    existing = [
        row
        for row in read_jsonl(manifest_path)
        if row.get("cleanup_run_id") != SHORT_RUN_ID and row.get("run_id") != SHORT_RUN_ID
    ]
    rows = []
    for record in records:
        rows.append(
            {
                "cleanup_run_id": SHORT_RUN_ID,
                "run_id": SHORT_RUN_ID,
                "original_relative_path": record.get("original_relative_path", ""),
                "replacement_path": record.get("replacement_path", ""),
                "archive_relative_path": record.get("archive_relative_path", ""),
                "classification": record.get("classification", ""),
                "reason": record.get("reason", ""),
                "size_bytes": record.get("size_bytes", 0),
                "sha256": record.get("sha256", ""),
                "replacement_sha256": record.get("replacement_sha256", ""),
                "archive_sha256": record.get("archive_sha256", ""),
                "hash_verified": record.get("hash_verified", record.get("archive_copy_verified", False)),
                "archived_at": record.get("archived_at", ""),
                "removed_from_repo_at": record.get("removed_from_repo_at", ""),
                "deleted_at": record.get("deleted_at", ""),
                "archive_path_redacted": True,
            }
        )
    write_jsonl(manifest_path, [*existing, *rows])


def status_event(report: Mapping[str, Any], *, report_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "event_type": "diagnostic_v4_7_6_eval_artifact_archive_purge_nonprod",
        "status": STATUS,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": report_sha256},
        "diagnostic_only": True,
        "non_production": True,
        "cleanup_only": True,
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
        "external_archive_target_resolved": report["external_archive_target_resolved"],
        "external_archive_target_redacted": True,
        "archived_count": report["archived_count"],
        "removed_count": report["removed_count"],
        "delete_only_count": report["delete_only_count"],
        "deleted_count": report["deleted_count"],
        "manual_hold_count": report["manual_hold_count"],
        "archive_copy_failed_count": report["archive_copy_failed_count"],
        "hash_verification_failed_count": report["hash_verification_failed_count"],
        "cleanup_manifest_path": report["cleanup_manifest_path"],
        "archive_manifest_path": report["archive_manifest_path"],
    }


def append_status(root: Path, report: Mapping[str, Any], *, report_sha256: str) -> None:
    status_path = root / STATUS_JSONL_PATH
    existing = [
        row
        for row in read_jsonl(status_path)
        if row.get("short_run_id") != SHORT_RUN_ID and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
    ]
    write_jsonl(status_path, [*existing, status_event(report, report_sha256=report_sha256)])


def upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    start = f"<!-- {SHORT_RUN_ID}:progress-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:progress-entry:end -->"
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        "This is cleanup/refactor only: current lineage reports now resolve through short keys "
        "`v4_7_preofficial`, `v4_7_2`, `v4_7_3`, `v4_7_4`, `v4_7_5`, and `current`. "
        f"External archive target resolved={str(report['external_archive_target_resolved']).lower()} and redacted; "
        f"archived {report['archived_count']} files, removed {report['removed_count']}, deleted transient cache "
        f"{report['deleted_count']}, and held {report['manual_hold_count']} ambiguous/generated surfaces for manual review. "
        f"Repo-local report files moved {report['repo_local_report_file_count_before']} -> "
        f"{report['repo_local_report_file_count_after']} and bytes {report['repo_local_report_bytes_before']} -> "
        f"{report['repo_local_report_bytes_after']}. Protected namespaces remain untouched. This does not run retrieval, "
        "EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, "
        "denominator mutation, training, FT-A, fine_tuning, promotion, product-success, or live readiness."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: .*? KST\.", "Last updated: 2026-05-30 KST.", text, count=1)
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    anchor = "for behavior-changing runs or explicit forensic evidence requirements.\n"
    text = upsert_block(text, start_marker=start, end_marker=end, block=block, after_anchor=anchor)
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    start = f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->"
    block = f"""### v4_7_6 Eval Artifact Archive And Purge

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: cleanup/refactor counters only. No retrieval, EvidenceBundle, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Before | After |
|---|---:|---:|
| repo_local_report_file_count | {report['repo_local_report_file_count_before']} | {report['repo_local_report_file_count_after']} |
| repo_local_report_bytes | {report['repo_local_report_bytes_before']} | {report['repo_local_report_bytes_after']} |
| long_path_literal_count | {report['long_path_literal_count_before']} | {report['long_path_literal_count_after']} |
| direct_report_path_dependency_count | {report['direct_report_path_dependency_count_before']} | {report['direct_report_path_dependency_count_after']} |
| archived_count | 0 | {report['archived_count']} |
| removed_count | 0 | {report['removed_count']} |
| deleted_count | 0 | {report['deleted_count']} |
| manual_hold_count | 0 | {report['manual_hold_count']} |
"""
    text = path.read_text(encoding="utf-8")
    text = upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    start = f"<!-- {SHORT_RUN_ID}:triage-entry:start -->"
    end = f"<!-- {SHORT_RUN_ID}:triage-entry:end -->"
    block = f"""### v4_7_6 Eval Artifact Cleanup Decision Boundary

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- KEEP_PROTECTED: eval queries, source registry, indexes, silver, source-of-truth/gold/qrels/denominator surfaces, raw user review evidence, and non-generated source/test/doc files.
- KEEP_CURRENT_MINIMAL: status ledger, archive manifest, v4_7 lineage short report paths, and current resolver-required compatibility reports.
- ARCHIVE_THEN_REMOVE: verified ignored/generated legacy diagnostic payloads already represented by report/status/docs. Archive copies are hash-verified before repo-local removal.
- DELETE_ONLY: transient Python/pytest caches and empty directories.
- REVIEW_MANUAL_HOLD: ambiguous generated-looking files, raw local path/source disclosure risks, and anything still referenced by tests/docs/core. Held count: {report['manual_hold_count']}.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
"""
    text = path.read_text(encoding="utf-8")
    text = upsert_block(text, start_marker=start, end_marker=end, block=block)
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` is cleanup/refactor only and writes `{SHORT_REPORT_PATH.as_posix()}`; it does not replay retrieval, EvidenceBundle, or answer generation.
- Resolver wiring: use `current` or `v4_7_6` for the latest cleanup report, and short lineage keys `v4_7_preofficial`, `v4_7_2`, `v4_7_3`, `v4_7_4`, and `v4_7_5` for preserved current-profile provenance.
- v4_7 lineage preserved: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with source-grounded Korean query candidates, hydrated rows 204, PDF 100, XLSX 104, and non-empty `질의문` 204; v4_7_3 applies the user-reviewed Korean query candidate CSV with `미검수=통과`; v4_7_4 replays PDF survivor 58 rows only; v4_7_5 repairs the PDF survivor EvidenceBundle diagnostic window.
- Cleanup counters: archived {report['archived_count']} generated files, removed {report['removed_count']} after hash verification, deleted {report['deleted_count']} transient cache entries, and held {report['manual_hold_count']} ambiguous/generated surfaces.
- Report surface: repo-local report files {report['repo_local_report_file_count_before']} -> {report['repo_local_report_file_count_after']}; report bytes {report['repo_local_report_bytes_before']} -> {report['repo_local_report_bytes_after']}. External archive target is used only as a redacted repo-external runtime archive.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; no per-run Markdown is created.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not threshold tuning, not winner selection, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## 전체 구조)", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path) -> None:
    path = root / "ai" / "eval" / "README.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    marker = f"- v4_7_6 cleanup/refactor: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` through `ai/scripts/rag_eval.py`; use resolver key `current` for this report and short lineage keys for v4_7_preofficial/v4_7_2/v4_7_3/v4_7_4/v4_7_5 provenance."
    if marker not in text:
        text = text.replace(f"- Current RAG status: `{STATUS}`", f"- Current RAG status: `{STATUS}`\n{marker}", 1)
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path) -> None:
    path = root / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    replacement = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        f"`{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` while current lineage resolves through short keys. |"
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
    previous_report_path = root / SHORT_REPORT_PATH
    previous_report = read_json(previous_report_path) if execute and previous_report_path.exists() else {}
    previous_cleanup_records = read_jsonl(root / CLEANUP_MANIFEST_PATH) if execute else []
    before_report_counts = count_report_tree(root)
    before_class_counts = count_classifications(root)
    before_couplings = scan_text_couplings(root)
    records, target = run_cleanup(root, execute=execute, generated_at=generated_at)
    if previous_cleanup_records:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for row in [*previous_cleanup_records, *records]:
            key = (str(row.get("original_relative_path", "")), str(row.get("classification", "")))
            merged[key] = row
        records = list(merged.values())
    if execute:
        write_jsonl(root / CLEANUP_MANIFEST_PATH, records)
        append_archive_manifest(root, records)
    after_report_counts = count_report_tree(root)
    after_class_counts = count_classifications(root)
    after_couplings = scan_text_couplings(root)

    archived_count = sum(1 for row in records if row.get("classification") == "ARCHIVE_THEN_REMOVE" and row.get("archived_at"))
    removed_count = sum(1 for row in records if row.get("removed_from_repo_at"))
    deleted_count = sum(1 for row in records if row.get("classification") == "DELETE_ONLY" and row.get("deleted_at"))
    archive_failed = sum(1 for row in records if row.get("classification") == "ARCHIVE_COPY_FAILED")
    hash_failed = sum(1 for row in records if row.get("archive_sha256") and row.get("archive_sha256") != row.get("sha256"))
    manual_hold_count = after_class_counts.get("REVIEW_MANUAL_HOLD", 0)
    prior_lineage_keys = tuple(key for key in CURRENT_LINEAGE_KEYS if key != LOGICAL_RUN_KEY)
    report: dict[str, Any] = {
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "cleanup_manifest_jsonl": CLEANUP_MANIFEST_PATH.as_posix(),
            "archive_manifest_jsonl": ARCHIVE_MANIFEST_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
        },
        "diagnostic_only": True,
        "non_production": True,
        "cleanup_only": True,
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
        "inventory_total_file_count": len(inventory_paths(root)[0]),
        "inventory_total_dir_count": len(inventory_paths(root)[1]),
        "keep_protected_count": after_class_counts.get("KEEP_PROTECTED", 0),
        "keep_current_minimal_count": after_class_counts.get("KEEP_CURRENT_MINIMAL", 0),
        "archive_then_remove_count": max(
            before_class_counts.get("ARCHIVE_THEN_REMOVE", 0),
            int(previous_report.get("archive_then_remove_count", 0) or 0),
            archived_count + archive_failed,
        ),
        "archived_count": archived_count,
        "removed_count": removed_count,
        "delete_only_count": max(
            before_class_counts.get("DELETE_ONLY", 0),
            int(previous_report.get("delete_only_count", 0) or 0),
            deleted_count,
        ),
        "deleted_count": deleted_count,
        "manual_hold_count": manual_hold_count,
        "archive_copy_failed_count": archive_failed,
        "hash_verification_failed_count": hash_failed,
        "long_path_literal_count_before": int(
            previous_report.get("long_path_literal_count_before", before_couplings["long_path_literal_count"])
        ),
        "long_path_literal_count_after": after_couplings["long_path_literal_count"],
        "direct_report_path_dependency_count_before": int(
            previous_report.get(
                "direct_report_path_dependency_count_before",
                before_couplings["direct_report_path_dependency_count"],
            )
        ),
        "direct_report_path_dependency_count_after": after_couplings["direct_report_path_dependency_count"],
        "repo_local_report_file_count_before": int(
            previous_report.get("repo_local_report_file_count_before", before_report_counts["file_count"])
        ),
        "repo_local_report_file_count_after": after_report_counts["file_count"],
        "repo_local_report_bytes_before": int(
            previous_report.get("repo_local_report_bytes_before", before_report_counts["bytes"])
        ),
        "repo_local_report_bytes_after": after_report_counts["bytes"],
        "current_lineage_short_path_migrated": all(
            registry.resolve_run(key, root=root).report_path.exists() for key in prior_lineage_keys
        ),
        "resolver_current_key_valid": registry.resolve_run("current", root=root).logical_key == LOGICAL_RUN_KEY,
        "resolver_legacy_aliases_minimized": False,
        "physical_cleanup_skipped_reason": "" if target.resolved else target.skip_reason,
        "cleanup_manifest_path": CLEANUP_MANIFEST_PATH.as_posix(),
        "archive_manifest_path": ARCHIVE_MANIFEST_PATH.as_posix(),
        "classification_summary_after": after_class_counts,
        "cleanup_record_count": len(records),
        "archive_hash_verification_pass_count": archived_count,
        "dry_run": not execute,
        "residual_risks": [
            "legacy long run ids remain as provenance and compatibility aliases",
            "ambiguous generated artifacts stay REVIEW_MANUAL_HOLD",
            "metrics remain cleanup counters only, not official quality metrics",
            "protected source-of-truth namespaces are not moved or deleted",
        ],
    }
    if sync_surfaces:
        update_docs(root, report)
        after_doc_couplings = scan_text_couplings(root)
        report["long_path_literal_count_after"] = after_doc_couplings["long_path_literal_count"]
        report["direct_report_path_dependency_count_after"] = after_doc_couplings[
            "direct_report_path_dependency_count"
        ]
    return report


def check_report(report: Mapping[str, Any]) -> None:
    required_false = (
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
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_6 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_6 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_6 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("cleanup_only") is not True:
        raise ValueError("v4_7_6 cleanup-only flags mismatch")
    for key in required_false:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_6 closed guardrail mismatch: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_6 official_metric_input_rows must stay zero")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_6 protected namespaces were touched")
