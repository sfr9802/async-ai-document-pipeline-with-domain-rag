"""Compile deterministic PDF/XLSX diagnostic answer drafts from evidence objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AI_WORKER_ROOT.parent

SCHEMA_VERSION = "rag_pdf_xlsx_deterministic_compiled_answers_v1"
POLICY_SHAPE = "NOT_ANSWERABLE_OR_POLICY_PENDING"
KEYWORD_FORBIDDEN_SHAPE = "KEYWORD_ECHO_FORBIDDEN"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence_rows = read_jsonl(Path(args.evidence_objects))
    compiled_rows = compile_evidence_rows(evidence_rows, run_id=args.run_id or utc_run_id())
    write_jsonl(Path(args.output), compiled_rows)
    print_json(
        {
            "status": "PASS",
            "schema_version": SCHEMA_VERSION,
            "output": repo_relative(Path(args.output)),
            "row_count": len(compiled_rows),
            "compiled_answer_count": sum(1 for row in compiled_rows if clean(nested(row, "compiled_answer", "answer"))),
            "abstain_count": sum(1 for row in compiled_rows if clean(nested(row, "compiled_answer", "abstain_reason"))),
            "keyword_echo_forbidden_count": sum(
                1
                for row in compiled_rows
                if clean(nested(row, "compiled_answer", "answer_shape")) == KEYWORD_FORBIDDEN_SHAPE
            ),
            "promotion_evidence": False,
            "external_live_llm_run": False,
            "optional_judge_run": False,
        }
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-objects", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", default="")
    return parser.parse_args(argv)


def compile_evidence_rows(
    evidence_rows: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    return [compile_evidence_row(row, run_id=run_id) for row in evidence_rows]


def compile_evidence_row(row: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    evidence = row.get("evidence_object") if isinstance(row.get("evidence_object"), Mapping) else {}
    expected_shape = clean(row.get("expected_answer_shape"))
    track = clean(row.get("track")).upper()
    policy_pending = parse_bool(row.get("policy_pending"))
    allowed = parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed"))
    blocker = clean(row.get("fail_closed_reason") or row.get("answer_disallowed_reason") or row.get("answer_generation_blocker"))
    keyword_only = parse_bool(row.get("keyword_only_evidence"))
    locator_only = parse_bool(row.get("locator_only_evidence"))

    if policy_pending or expected_shape == POLICY_SHAPE:
        compiled_answer = abstain_answer(
            shape=POLICY_SHAPE,
            reason=clean(row.get("policy_pending_reason")) or "policy pending",
            failure_mode=blocker or "POLICY_PENDING",
        )
        status = "POLICY_PENDING"
    elif keyword_only or blocker in {"KEYWORD_ECHO_FORBIDDEN", "XLSX_KEYWORD_ONLY", "PDF_KEYWORD_ONLY"}:
        compiled_answer = abstain_answer(
            shape=KEYWORD_FORBIDDEN_SHAPE,
            reason="Only keyword evidence was available; keyword echo is forbidden.",
            failure_mode=blocker or "KEYWORD_ECHO_FORBIDDEN",
        )
        status = "KEYWORD_ECHO_FORBIDDEN"
    elif locator_only or blocker in {"LOCATOR_ONLY_WITHOUT_CONTENT", "XLSX_LOCATOR_ONLY", "PDF_LOCATOR_ONLY"}:
        compiled_answer = abstain_answer(
            shape=POLICY_SHAPE,
            reason="Only locator evidence was available; no content claim was compiled.",
            failure_mode=blocker or "LOCATION_ONLY_ANSWER",
        )
        status = "LOCATOR_ONLY_ABSTAIN"
    elif not allowed:
        compiled_answer = abstain_answer(
            shape=POLICY_SHAPE,
            reason=blocker or "content evidence missing",
            failure_mode="INSUFFICIENT_CONTEXT",
        )
        status = "CONTENT_MISSING_ABSTAIN"
    else:
        compiled_answer = compile_allowed_answer(row, evidence, expected_shape=expected_shape, track=track)
        status = "COMPILED" if clean(compiled_answer.get("answer")) else "CONTENT_MISSING_ABSTAIN"

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "source_evidence_run_id": clean(row.get("run_id")),
        "source_input_run_id": clean(row.get("source_input_run_id")),
        "row_index": row.get("row_index"),
        "track": track,
        "query_id": clean(row.get("query_id")),
        "query": clean(row.get("query")),
        "expected_answer_shape": expected_shape,
        "expected_answer_text": clean(row.get("expected_answer_text")),
        "must_contain_terms": string_list(row.get("must_contain_terms")),
        "answer_allowed": allowed,
        "answer_generation_allowed": allowed,
        "answer_generation_blocker": blocker,
        "answer_disallowed_reason": blocker,
        "fail_closed_reason": blocker,
        "content_source_fields": string_list(row.get("content_source_fields")),
        "evidence_quality": row.get("evidence_quality") if isinstance(row.get("evidence_quality"), Mapping) else {},
        "policy_pending": policy_pending,
        "policy_pending_reason": clean(row.get("policy_pending_reason")),
        "compiler_status": status,
        "compiled_answer_draft": compiled_answer,
        "compiled_answer": compiled_answer,
        "compiled_answer_json": json.dumps(compiled_answer, ensure_ascii=False, sort_keys=True),
        "evidence_object": dict(evidence),
        "content_summary": clean(row.get("content_summary")),
        "context_available": parse_bool(row.get("context_available")),
        "context_has_expected_terms": parse_bool(row.get("context_has_expected_terms")),
        "dry_run_preview_used_as_actual_answer": False,
        "local_llm_run": False,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "guardrails": diagnostic_guardrails(),
    }


def compile_allowed_answer(
    row: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    expected_shape: str,
    track: str,
) -> dict[str, Any]:
    if expected_shape == "TABLE_ROW_VALUE":
        answer = compile_table_row_value(evidence)
    elif expected_shape == "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT":
        answer = compile_table_range_context(evidence)
    elif expected_shape == "PDF_SECTION_WITH_SUMMARY":
        answer = compile_pdf_section_summary(evidence)
    elif expected_shape == "PDF_TABLE_VALUE_WITH_CONTEXT":
        answer = compile_pdf_table_value(evidence)
    elif expected_shape in {"LOCATION_PLUS_CONTENT", "EVIDENCE_LOCATOR_WITH_CONTENT"}:
        answer = compile_location_plus_content(evidence, track=track)
    elif expected_shape == "YES_NO_WITH_EVIDENCE":
        answer = compile_yes_no_with_evidence(evidence)
    else:
        answer = clean(evidence.get("content_summary"))

    if not answer:
        return abstain_answer(
            shape=POLICY_SHAPE,
            reason="Evidence was present but did not contain the required row/column/value or summary fields.",
            failure_mode="INSUFFICIENT_CONTEXT",
        )
    citation = citation_for(evidence, answer)
    return {
        "answer": answer,
        "answer_shape": expected_shape,
        "citations": [citation] if citation else [],
        "abstain_reason": "",
        "used_content_terms": used_content_terms(row, evidence, answer),
        "failure_mode_if_any": "",
    }


def compile_table_row_value(evidence: Mapping[str, Any]) -> str:
    row_label = clean(evidence.get("row_label"))
    column_label = clean(evidence.get("column_label")) or first_nonempty(string_list(evidence.get("column_labels")))
    value = clean(evidence.get("value"))
    if not value:
        for row_value in mapping_list(evidence.get("row_values")):
            value = clean(row_value.get("value"))
            if value:
                break
    if not (row_label and column_label and value):
        return ""
    scope = xlsx_scope(evidence)
    return f"{row_label} row / {column_label} column value is {value}. {scope}".strip()


def compile_table_range_context(evidence: Mapping[str, Any]) -> str:
    summary = clean(evidence.get("content_summary"))
    headers = string_list(evidence.get("header_context"))
    inferred = clean(evidence.get("inferred_table_context"))
    scope = xlsx_scope(evidence)
    row_values = mapping_list(evidence.get("row_values"))
    if not summary and row_values:
        summary = "; ".join(clean(item.get("row_text") or item.get("value")) for item in row_values if clean(item.get("row_text") or item.get("value")))
    if not summary:
        return ""
    if inferred and inferred not in summary:
        summary = f"{summary} Inferred table context: {inferred}."
    header_text = f" Major headers: {', '.join(headers[:8])}." if headers else ""
    return f"{summary} {scope}{header_text}".strip()


def compile_pdf_section_summary(evidence: Mapping[str, Any]) -> str:
    summary = clean(evidence.get("content_summary")) or clean(evidence.get("paragraph_block_text"))
    if not summary:
        return ""
    page = clean(evidence.get("page") or evidence.get("page_label"))
    section = clean(evidence.get("section"))
    location = f" Page {page}" if page else ""
    if section:
        location += f", section {section}"
    return f"{summary}{location}.".strip()


def compile_pdf_table_value(evidence: Mapping[str, Any]) -> str:
    row_label = clean(evidence.get("row_label"))
    column_label = clean(evidence.get("column_label")) or first_nonempty(string_list(evidence.get("column_labels")))
    value = clean(evidence.get("value"))
    unit = clean(evidence.get("unit"))
    page = clean(evidence.get("page") or evidence.get("page_label"))
    if not (row_label and value):
        return ""
    column_part = f" / {column_label} column" if column_label else ""
    unit_part = f" ({unit})" if unit else ""
    page_part = f" on page {page}" if page else ""
    return f"{row_label}{column_part} value is {value}{unit_part}{page_part}."


def compile_location_plus_content(evidence: Mapping[str, Any], *, track: str) -> str:
    summary = clean(evidence.get("content_summary")) or clean(evidence.get("paragraph_block_text"))
    if not summary:
        return ""
    if track == "XLSX":
        return f"{summary} {xlsx_scope(evidence)}".strip()
    page = clean(evidence.get("page") or evidence.get("page_label"))
    suffix = f" Page {page}." if page else ""
    return f"{summary}{suffix}".strip()


def compile_yes_no_with_evidence(evidence: Mapping[str, Any]) -> str:
    summary = clean(evidence.get("content_summary"))
    if not summary:
        return ""
    return f"Yes. {summary}"


def xlsx_scope(evidence: Mapping[str, Any]) -> str:
    parts = []
    if clean(evidence.get("table_title")):
        parts.append(f"table {clean(evidence.get('table_title'))}")
    if clean(evidence.get("sheet")):
        parts.append(f"sheet {clean(evidence.get('sheet'))}")
    if clean(evidence.get("range")):
        parts.append(f"range {clean(evidence.get('range'))}")
    return f"Evidence scope: {', '.join(parts)}." if parts else ""


def citation_for(evidence: Mapping[str, Any], claim: str) -> dict[str, Any]:
    locator = evidence.get("locator") if isinstance(evidence.get("locator"), Mapping) else {}
    if not locator:
        locator = {
            key: evidence.get(key)
            for key in ("file_name", "document_version_id", "sheet", "range", "cell", "page", "bbox", "section")
            if evidence.get(key) not in (None, "", [], {})
        }
    return {
        "locator": locator,
        "supports_claim": True,
        "claim": claim,
    }


def used_content_terms(row: Mapping[str, Any], evidence: Mapping[str, Any], answer: str) -> list[str]:
    del row
    candidates = [
        clean(evidence.get("row_label")),
        clean(evidence.get("column_label")),
        clean(evidence.get("value")),
    ]
    for item in [
        *mapping_list(evidence.get("row_values")),
        *mapping_list(evidence.get("column_values")),
        *mapping_list(evidence.get("cell_values")),
    ]:
        candidates.extend(
            [
                clean(item.get("row_label")),
                clean(item.get("column_label")),
                clean(item.get("value")),
                clean(item.get("row_text")),
                clean(item.get("column_text")),
            ]
        )
    candidates.extend(string_list(evidence.get("table_context")))
    candidates.extend(string_list(evidence.get("nearby_rows")))
    summary_terms = [
        term
        for term in re.split(r"[\s,.;:|/]+", clean(evidence.get("content_summary")))
        if len(term) >= 2
    ][:8]
    candidates.extend(summary_terms)
    seen = set()
    used = []
    for term in candidates:
        if not term or term in seen:
            continue
        if normalize(term) in normalize(answer):
            used.append(term)
            seen.add(term)
    return used[:12]


def abstain_answer(*, shape: str, reason: str, failure_mode: str) -> dict[str, Any]:
    return {
        "answer": "",
        "answer_shape": shape,
        "citations": [],
        "abstain_reason": reason,
        "used_content_terms": [],
        "failure_mode_if_any": failure_mode,
    }


def diagnostic_guardrails() -> dict[str, bool]:
    return {
        "retrieval_tuning_run": False,
        "reranking_run": False,
        "parser_expansion_run": False,
        "threshold_relaxation_run": False,
        "db_mutation_run": False,
        "searchunit_mutation_run": False,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
        "existing_gold_csv_overwritten": False,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def nested(row: Mapping[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    if not text:
        return []
    return [clean(item) for item in re.split(r"[;|]", text) if clean(item)]


def first_nonempty(values: Iterable[str]) -> str:
    for value in values:
        if clean(value):
            return clean(value)
    return ""


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def normalize(value: object) -> str:
    return re.sub(r"\s+", "", clean(value)).lower()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
