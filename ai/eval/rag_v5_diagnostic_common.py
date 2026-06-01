from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    resolved = Path(path)
    if not resolved.exists():
        return []
    return [json.loads(line) for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path | str, rows: Iterable[Mapping[str, Any]]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path | str) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def write_report_bundle(
    root: Path | str,
    report_path: Path | str,
    report: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    payload = json_clone(report)
    resolved_report_path = Path(root) / report_path
    write_json(resolved_report_path, payload)
    return payload, {"report_json_sha256": sha256_file(resolved_report_path)}


def artifact_status(path: Path | str) -> str:
    return "present" if Path(path).exists() else "materialized_in_memory"


def upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        text = pattern.sub("", text, count=1)
    return wrapped + "\n\n" + text.lstrip()


def sync_last_updated(text: str, kst_doc_date: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {kst_doc_date} KST.", text, count=1)


def replace_summary_block(
    text: str,
    *,
    start_marker: str,
    end_marker: str,
    block: str,
    marker_pattern: str,
    legacy_pattern: str | None = None,
) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    marked_summary = re.compile(marker_pattern, re.S)
    if marked_summary.search(text):
        return marked_summary.sub(wrapped, text, count=1)
    if legacy_pattern:
        legacy_summary = re.compile(legacy_pattern, re.S)
        if legacy_summary.search(text):
            return legacy_summary.sub(wrapped, text, count=1)
    return wrapped + "\n\n" + text.lstrip()


def assert_no_raw_payload_keys(value: Any, forbidden_keys: set[str], *, context: str) -> None:
    if isinstance(value, Mapping):
        overlap = forbidden_keys & set(value)
        if overlap:
            raise ValueError(f"{context} raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            assert_no_raw_payload_keys(child, forbidden_keys, context=context)
    elif isinstance(value, list):
        for child in value:
            assert_no_raw_payload_keys(child, forbidden_keys, context=context)
