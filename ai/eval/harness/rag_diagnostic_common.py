"""Shared helpers for RAG diagnostic and tuning artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"
V4_7_6_ARCHIVE_RUN_ID = "v4_7_6_eval_artifact_archive_purge"
EXTERNAL_ARCHIVE_ENV_KEYS = ("RAG_EVAL_EXTERNAL_ARCHIVE_ROOT", "EXTERNAL_RUNTIME_ARTIFACTS_ROOT")
DEFAULT_EXTERNAL_ARCHIVE_ROOTS = (
    Path("D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline"),
)
LEGACY_EXTERNAL_REPORT_ARCHIVE_DIRS = (
    Path(
        "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
        "rag-ingestion/repo-wide-cleanup-20260521/reports/rag-ingestion-legacy"
    ),
    Path(
        "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
        "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
    ),
)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def windows_long_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    path_text = str(path)
    if path_text.startswith("\\\\?\\"):
        return path
    if path.is_absolute():
        return Path("\\\\?\\" + path_text)
    return path


def external_archive_namespace_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for key in EXTERNAL_ARCHIVE_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            roots.append(Path(value))
    roots.extend(DEFAULT_EXTERNAL_ARCHIVE_ROOTS)

    namespaces: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        namespace = root / "rag-ingestion" / V4_7_6_ARCHIVE_RUN_ID
        if is_relative_to(namespace, ROOT):
            continue
        key = str(namespace).casefold()
        if key not in seen:
            seen.add(key)
            namespaces.append(windows_long_path(namespace))
    return tuple(namespaces)


def _repo_relative_or_none(path: Path) -> Path | None:
    try:
        return path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None


def resolve_report_artifact_path(path: Path) -> Path:
    if path.exists():
        return path

    rel = _repo_relative_or_none(path)
    if rel is not None and rel.as_posix().startswith("ai/eval/reports/rag-ingestion/"):
        for archive_root in external_archive_namespace_roots():
            archived = archive_root / rel
            if archived.exists():
                return archived

    if path.parent == REPORT_ARCHIVE_DIR:
        for archive_dir in LEGACY_EXTERNAL_REPORT_ARCHIVE_DIRS:
            archived = windows_long_path(archive_dir / path.name)
            if archived.exists():
                return archived
        return path

    if path.parent == REPORT_DIR:
        for archive_dir in LEGACY_EXTERNAL_REPORT_ARCHIVE_DIRS:
            archived = windows_long_path(archive_dir / path.name)
            if archived.exists():
                return archived
        archived_local = REPORT_ARCHIVE_DIR / path.name
        if archived_local.exists():
            return archived_local

    return path


def artifact_exists(path: Path) -> bool:
    return resolve_report_artifact_path(path).exists()


def artifact_is_file(path: Path) -> bool:
    return resolve_report_artifact_path(path).is_file()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return "" if value is None else str(value)


def repo_relative(path: Path, *, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(resolve_report_artifact_path(path).read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with resolve_report_artifact_path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def csv_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "|".join(clean(item) for item in value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return clean(value)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns or (rows[0].keys() if rows else ()))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def artifact_sha256_without_summary(outputs: Mapping[str, Path]) -> dict[str, str]:
    return {
        f"{key}_sha256": sha256_file(path)
        for key, path in outputs.items()
        if key != "summary_json"
    }


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    marked = f"{start}\n{entry.rstrip()}\n{end}\n"
    pattern = rf"{re.escape(start)}.*?{re.escape(end)}\n?"
    if re.search(pattern, text, flags=re.DOTALL):
        text = re.sub(pattern, marked, text, count=1, flags=re.DOTALL)
    else:
        insertion_candidates = [index for index in (text.find("\n<!-- "), text.find("\n## ")) if index != -1]
        insert_at = min(insertion_candidates) if insertion_candidates else -1
        if insert_at == -1:
            text = text.rstrip() + "\n\n" + marked
        else:
            text = text[:insert_at].rstrip() + "\n\n" + marked + "\n" + text[insert_at:].lstrip("\n")
    path.write_text(text, encoding="utf-8")
