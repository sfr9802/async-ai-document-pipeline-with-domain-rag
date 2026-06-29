from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


ANSWERABILITY_VALUES = {"answerable", "unanswerable", "unknown"}


class DatasetSchemaError(ValueError):
    """Raised when the eval dataset shape is not executable."""


@dataclass(frozen=True)
class ExpectedEvidence:
    doc_id: str = ""
    chunk_id: str = ""
    text: str = ""
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvalItem:
    id: str
    query: str
    answerability: str = "unknown"
    expected_answer: str = ""
    expected_answer_aliases: tuple[str, ...] = ()
    expected_evidence: tuple[ExpectedEvidence, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str = ""
    has_answerability_label: bool = False
    validation_warnings: tuple[str, ...] = ()
    source_row: Mapping[str, Any] = field(default_factory=dict)

    @property
    def has_expected_answer(self) -> bool:
        return bool(_clean(self.expected_answer) or any(_clean(alias) for alias in self.expected_answer_aliases))

    @property
    def has_expected_evidence(self) -> bool:
        return bool(self.expected_evidence)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _first_clean(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not (text.startswith("{") or text.startswith("[")):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetSchemaError(f"{path}:{line_no}: invalid JSONL row: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise DatasetSchemaError(f"{path}:{line_no}: each JSONL row must be an object")
        rows.append(row)
    return rows


def _load_dataset_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DatasetSchemaError(f"dataset does not exist: {path}")
    if path.suffix.lower() == ".jsonl":
        return _read_jsonl_rows(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise DatasetSchemaError(f"{path}: JSON dataset must be a list of objects")
        if not all(isinstance(row, dict) for row in payload):
            raise DatasetSchemaError(f"{path}: JSON dataset entries must be objects")
        return list(payload)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise DatasetSchemaError(f"{path}: CSV dataset must include a header row")
            return [dict(row) for row in reader]
    raise DatasetSchemaError(f"{path}: unsupported dataset extension; expected .jsonl, .json, or .csv")


def _canonical_answerability(row: Mapping[str, Any]) -> tuple[str, bool]:
    raw = _first_clean(row, "answerability", "answerability_label")
    if raw:
        normalized_raw = raw.strip().lower()
        if normalized_raw in {"3", "answerable", "answered", "yes", "true"}:
            return "answerable", True
        if normalized_raw in {"1", "unanswerable", "no", "false"}:
            return "unanswerable", True
        if normalized_raw in {"0", "2", "unknown", "unknown_answerability", "not_evaluated"}:
            return "unknown", True
        return normalized_raw, True
    label = _first_clean(row, "normalized_answerability_label", "user_answerability_label")
    if not label:
        return "unknown", False
    normalized = label.strip().upper()
    if "UNANSWERABLE" in normalized:
        return "unanswerable", True
    if normalized.startswith("ANSWERABLE"):
        return "answerable", True
    return "unknown", False


def _expected_answer_aliases(row: Mapping[str, Any]) -> list[str]:
    raw = row.get("expected_answer_aliases") or row.get("aliases") or []
    parsed = _parse_jsonish(raw)
    if isinstance(parsed, list):
        return [_clean(alias) for alias in parsed if isinstance(alias, str) and _clean(alias)]
    if isinstance(parsed, str) and _clean(parsed):
        return [_clean(parsed)]
    return []


def _locator_evidence_fields(row: Mapping[str, Any]) -> tuple[str, str]:
    locator = _parse_jsonish(row.get("citation_locator"))
    if not isinstance(locator, Mapping):
        return "", ""
    cited_chunk_ids = locator.get("cited_chunk_ids")
    chunk_id = ""
    if isinstance(cited_chunk_ids, list) and cited_chunk_ids:
        chunk_id = _clean(cited_chunk_ids[0])
    return (
        _clean(locator.get("file") or locator.get("document_version_id")),
        _clean(locator.get("search_unit_id") or locator.get("chunk_id") or chunk_id),
    )


def _expected_evidence_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("expected_evidence")
    parsed = _parse_jsonish(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    if raw is not None and _clean(raw):
        return parsed  # type: ignore[return-value]
    text = _first_clean(
        row,
        "supporting_evidence",
        "supporting_evidence_note",
        "citation_text",
        "expected_evidence_text_or_summary",
        "user_expected_evidence_text_or_summary",
        "evidence_summary",
    )
    if not text:
        return []
    doc_id, chunk_id = _locator_evidence_fields(row)
    return [{"doc_id": doc_id, "chunk_id": chunk_id, "text": text, "required": True}]


def load_eval_dataset(path: Path | str) -> list[EvalItem]:
    rows = _load_dataset_rows(Path(path))
    items: list[EvalItem] = []
    seen: set[str] = set()
    for ordinal, row in enumerate(rows, start=1):
        row_id = _clean(row.get("id") or row.get("query_id"))
        context = row_id or f"<row:{ordinal}>"
        if not row_id:
            raise DatasetSchemaError(f"{context}: id is required")
        if row_id in seen:
            raise DatasetSchemaError(f"{row_id}: duplicate id")
        seen.add(row_id)
        query = _first_clean(row, "query", "query_text", "question", "question_ko")
        if not query:
            raise DatasetSchemaError(f"{row_id}: query is required")

        warnings: list[str] = []
        answerability, has_answerability_label = _canonical_answerability(row)
        if not has_answerability_label:
            warnings.append("missing_answerability_label")
        if answerability not in ANSWERABILITY_VALUES:
            raise DatasetSchemaError(
                f"{row_id}: answerability must be one of answerable, unanswerable, unknown"
            )

        aliases = _expected_answer_aliases(row)
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            raise DatasetSchemaError(f"{row_id}: expected_answer_aliases must be a list of strings")

        evidence_rows = _expected_evidence_rows(row)
        if not isinstance(evidence_rows, list):
            raise DatasetSchemaError(f"{row_id}: expected_evidence must be a list")
        evidence: list[ExpectedEvidence] = []
        for index, evidence_row in enumerate(evidence_rows, start=1):
            if not isinstance(evidence_row, dict):
                raise DatasetSchemaError(f"{row_id}: expected_evidence[{index}] must be an object")
            required_value = evidence_row.get("required", True)
            if not isinstance(required_value, bool):
                raise DatasetSchemaError(f"{row_id}: expected_evidence[{index}].required must be a boolean")
            ev = ExpectedEvidence(
                doc_id=_clean(evidence_row.get("doc_id") or evidence_row.get("docId")),
                chunk_id=_clean(evidence_row.get("chunk_id") or evidence_row.get("chunkId")),
                text=_clean(evidence_row.get("text")),
                required=required_value,
            )
            if not (ev.doc_id or ev.chunk_id or ev.text):
                raise DatasetSchemaError(
                    f"{row_id}: expected_evidence[{index}] must include doc_id, chunk_id, or text"
                )
            evidence.append(ev)

        tags = row.get("tags") or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise DatasetSchemaError(f"{row_id}: tags must be a list of strings")

        item = EvalItem(
            id=row_id,
            query=query,
            answerability=answerability,
            expected_answer=_first_clean(
                row,
                "expected_answer",
                "expected_answer_ko",
                "expected_answer_text",
                "normalized_expected_answer_text",
                "user_expected_answer_text",
                "expected_answer_text_existing",
            ),
            expected_answer_aliases=tuple(_clean(alias) for alias in aliases if _clean(alias)),
            expected_evidence=tuple(evidence),
            tags=tuple(_clean(tag) for tag in tags if _clean(tag)),
            notes=_clean(row.get("notes")),
            has_answerability_label=has_answerability_label,
            validation_warnings=tuple(warnings),
            source_row=_jsonable(row),
        )
        if not item.has_expected_answer:
            warnings.append("missing_expected_answer")
        if not item.has_expected_evidence:
            warnings.append("missing_expected_evidence")
        if not item.expected_answer_aliases:
            warnings.append("missing_expected_answer_aliases")
        item = EvalItem(
            id=item.id,
            query=item.query,
            answerability=item.answerability,
            expected_answer=item.expected_answer,
            expected_answer_aliases=item.expected_answer_aliases,
            expected_evidence=item.expected_evidence,
            tags=item.tags,
            notes=item.notes,
            has_answerability_label=item.has_answerability_label,
            validation_warnings=tuple(warnings),
            source_row=item.source_row,
        )
        items.append(item)
    return items
