"""E2E baseline artifact helpers for pre-tuning A/B/C eval snapshots.

This module is intentionally file-based. It does not mutate indexes, call
SearchUnit claim paths, or promote any baseline. The live LLM path is opt-in;
the default dry-run mode verifies the I/O capture contract without network.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


VALID_GOLD_STATUSES = {"gold", "candidate", "diagnostic_only"}
VALID_VERDICTS = {
    "pass",
    "fail",
    "partial",
    "diagnostic_only",
    "needs_human_review",
}
FAILURE_TYPES = {
    "retrieval_miss",
    "wrong_context_rank",
    "context_truncation",
    "answer_not_grounded",
    "hallucination",
    "wrong_answerability",
    "partial_answer",
    "format_error",
    "prompt_regression",
    "unknown",
}

PROMPT_VERSION = "baseline-e2e-capture-v1"
DRY_RUN_MODEL = "dry-run-extractive-v0"
LIVE_ENV_FLAG = "E2E_BASELINE_LIVE_LLM"

SENSITIVE_KEY_RE = re.compile(
    r"(^|[_-])(api[_-]?key|secret|authorization|credential|password|"
    r"private[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"cookie|set[_-]?cookie|x[_-]?api[_-]?key)($|[_-])",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
API_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,})\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?82[-.\s]?)?0?1[016789][-. ]?\d{3,4}[-. ]?\d{4}\b")
KOREAN_RRN_RE = re.compile(r"\b\d{6}-[1-4]\d{6}\b")

REDACTED = "[REDACTED]"


def redaction_marker() -> str:
    return REDACTED


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: line {line_number} must be a JSON object")
            rows.append(payload)
    return rows


def redact(value: Any) -> Any:
    """Recursively redact secrets and likely PII from artifact payloads."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_RE.search(key_text):
                out[key_text] = REDACTED
            else:
                out[key_text] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        redacted = BEARER_RE.sub("Bearer " + REDACTED, value)
        redacted = API_KEY_RE.sub(REDACTED, redacted)
        redacted = EMAIL_RE.sub(REDACTED, redacted)
        redacted = PHONE_RE.sub(REDACTED, redacted)
        redacted = KOREAN_RRN_RE.sub(REDACTED, redacted)
        return redacted
    return value


def official_denominator_included(record: Mapping[str, Any]) -> bool:
    return record.get("gold_status") == "gold"


def validate_e2e_llm_io_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required_paths = [
        "run_id",
        "track",
        "case_id",
        "gold_status",
        "query",
        "retrieval.namespace",
        "retrieval.top_k",
        "retrieval.retrieved_doc_ids",
        "llm_input.model",
        "llm_input.prompt_version",
        "llm_input.temperature",
        "llm_input.messages",
        "llm_output.content",
        "llm_output.finish_reason",
        "usage.input_tokens",
        "usage.output_tokens",
        "usage.latency_ms",
        "judgement.answerability",
        "judgement.verdict",
        "judgement.grounded",
        "judgement.failure_type",
        "judgement.notes",
    ]
    for path in required_paths:
        if _path_get(record, path, missing_marker := object()) is missing_marker:
            errors.append(f"missing required field: {path}")

    retrieval = record.get("retrieval")
    if isinstance(retrieval, Mapping):
        if "index_version" not in retrieval and "index_identifier" not in retrieval:
            errors.append("missing required field: retrieval.index_version or retrieval.index_identifier")
    else:
        errors.append("retrieval must be an object")

    gold_status = record.get("gold_status")
    if gold_status not in VALID_GOLD_STATUSES:
        errors.append(f"invalid gold_status: {gold_status!r}")

    verdict = _path_get(record, "judgement.verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(f"invalid judgement.verdict: {verdict!r}")

    failure_type = _path_get(record, "judgement.failure_type")
    if failure_type is not None and failure_type not in FAILURE_TYPES:
        errors.append(f"invalid judgement.failure_type: {failure_type!r}")

    messages = _path_get(record, "llm_input.messages")
    if not isinstance(messages, list) or not messages:
        errors.append("llm_input.messages must be a non-empty list")

    retrieved_doc_ids = _path_get(record, "retrieval.retrieved_doc_ids")
    if not isinstance(retrieved_doc_ids, list):
        errors.append("retrieval.retrieved_doc_ids must be a list")

    return errors


def validate_jsonl_records(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        for error in validate_e2e_llm_io_record(row):
            errors.append(f"line {index}: {error}")
    return errors


def _path_get(record: Mapping[str, Any], path: str, default: Any = None) -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def make_messages(
    *,
    track: str,
    query: str,
    contexts: Sequence[Mapping[str, Any]],
    expected_evidence_ids: Sequence[str],
) -> list[dict[str, str]]:
    context_lines: list[str] = []
    for idx, context in enumerate(contexts[:10], start=1):
        text = clean(context.get("text") or context.get("content"))
        if len(text) > 1200:
            text = text[:1197] + "..."
        label_parts = [
            f"rank={context.get('rank')}",
            f"doc_id={context.get('doc_id') or context.get('source_file_name')}",
            f"chunk_id={context.get('chunk_id') or context.get('search_unit_id')}",
        ]
        context_lines.append(f"[{idx}] {'; '.join(label_parts)}\n{text}")

    if not context_lines:
        context_lines.append("[no retrieved context text available in source report]")

    return [
        {
            "role": "system",
            "content": (
                "Answer only from the provided retrieval context. If the context is "
                "insufficient, say that the answer is not supported by the context. "
                "Keep citations tied to retrieved evidence ids."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Track: {track}\n"
                f"Query: {query}\n"
                f"Expected evidence ids: {', '.join(expected_evidence_ids) or '(none)'}\n\n"
                "Retrieved context:\n"
                + "\n\n".join(context_lines)
            ),
        },
    ]


def dry_run_answer(messages: Sequence[Mapping[str, str]]) -> tuple[str, str]:
    user_content = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            user_content = clean(message.get("content"))
            break
    marker = "Retrieved context:"
    context = user_content.split(marker, 1)[1].strip() if marker in user_content else user_content
    if "[no retrieved context text available" in context:
        return (
            "E2E I/O capture path verified, live call not executed. "
            "No answer was generated because retrieved context text was unavailable.",
            "dry_run_no_context",
        )
    excerpt = context.replace("\n", " ").strip()
    if len(excerpt) > 500:
        excerpt = excerpt[:497] + "..."
    return (
        "E2E I/O capture path verified, live call not executed. "
        f"Dry-run extractive preview: {excerpt}",
        "dry_run",
    )


def build_io_record(
    *,
    run_id: str,
    track: str,
    case_id: str,
    gold_status: str,
    query: str,
    retrieval: Mapping[str, Any],
    messages: Sequence[Mapping[str, str]],
    output_content: str,
    finish_reason: str,
    model: str,
    temperature: float,
    latency_ms: float,
    answerability: str,
    verdict: str,
    grounded: bool,
    failure_type: str | None,
    notes: str,
    prompt_version: str = PROMPT_VERSION,
    seed: int | None = None,
    cost_usd: float | None = None,
) -> dict[str, Any]:
    input_tokens = approx_tokens(json.dumps(messages, ensure_ascii=False))
    output_tokens = approx_tokens(output_content)
    record = {
        "schema_version": "e2e_llm_io_v1",
        "run_id": run_id,
        "track": track,
        "case_id": case_id,
        "gold_status": gold_status,
        "query": query,
        "retrieval": dict(retrieval),
        "llm_input": {
            "model": model,
            "prompt_version": prompt_version,
            "temperature": temperature,
            "seed": seed,
            "messages": [dict(message) for message in messages],
        },
        "llm_output": {
            "content": output_content,
            "finish_reason": finish_reason,
        },
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": float(latency_ms),
            "cost_usd": cost_usd,
        },
        "judgement": {
            "answerability": answerability,
            "verdict": verdict,
            "grounded": bool(grounded),
            "failure_type": failure_type,
            "notes": notes,
        },
    }
    return redact(record)


def build_judgement_record(io_record: Mapping[str, Any]) -> dict[str, Any]:
    judgement = io_record["judgement"]
    retrieval = io_record["retrieval"]
    return {
        "schema_version": "e2e_judgement_v1",
        "run_id": io_record["run_id"],
        "track": io_record["track"],
        "case_id": io_record["case_id"],
        "gold_status": io_record["gold_status"],
        "answerability": judgement["answerability"],
        "verdict": judgement["verdict"],
        "grounded": judgement["grounded"],
        "failure_type": judgement["failure_type"],
        "evidence_hit": retrieval.get("evidence_hit"),
        "notes": judgement["notes"],
    }


def build_retrieval_record(io_record: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = io_record["retrieval"]
    return {
        "schema_version": "retrieval_result_v1",
        "run_id": io_record["run_id"],
        "track": io_record["track"],
        "case_id": io_record["case_id"],
        "gold_status": io_record["gold_status"],
        "query": io_record["query"],
        "namespace": retrieval.get("namespace"),
        "index_version": retrieval.get("index_version"),
        "index_identifier": retrieval.get("index_identifier"),
        "top_k": retrieval.get("top_k"),
        "retrieved_doc_ids": retrieval.get("retrieved_doc_ids", []),
        "expected_evidence_ids": retrieval.get("expected_evidence_ids", []),
        "evidence_hit": retrieval.get("evidence_hit"),
        "failure_type": io_record["judgement"].get("failure_type"),
    }


def judge_dry_run_case(
    *,
    gold_status: str,
    evidence_hit: bool | None,
    has_context_text: bool,
    label_status: str,
) -> tuple[str, str, bool, str | None, str]:
    if gold_status != "gold":
        return (
            "needs_human_review" if label_status in {"needs_review", "pending"} else "diagnostic",
            "diagnostic_only",
            bool(evidence_hit),
            "unknown" if evidence_hit is False else None,
            "Non-gold case is captured for raw I/O and failure analysis only.",
        )
    if evidence_hit is False:
        return (
            "answerable",
            "needs_human_review",
            False,
            "retrieval_miss",
            "Gold case lacks expected retrieval evidence; live LLM call was not executed.",
        )
    if not has_context_text:
        return (
            "answerable",
            "needs_human_review",
            False,
            "unknown",
            "Gold case has retrieval evidence but no raw context text in the source report; live LLM call was not executed.",
        )
    return (
        "answerable",
        "needs_human_review",
        True,
        None,
        "Dry-run captured prompt/output shape; live LLM call and human answer judgement were not executed.",
    )


def aggregate_summary(
    *,
    run_id: str,
    generated_at: str,
    io_records: Sequence[Mapping[str, Any]],
    source_metrics: Mapping[str, Mapping[str, Any]],
    live_call_executed: bool,
) -> dict[str, Any]:
    by_track: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in io_records:
        by_track[str(record.get("track"))].append(record)

    track_summaries = {
        track: summarize_track(records, source_metrics.get(track, {}), live_call_executed=live_call_executed)
        for track, records in sorted(by_track.items())
    }
    overall_counts = Counter(record.get("gold_status") for record in io_records)
    return {
        "schema_version": "e2e_baseline_summary_v1",
        "run_id": run_id,
        "generated_at": generated_at,
        "live_call_executed": live_call_executed,
        "denominator_policy": denominator_policy_summary(),
        "case_counts_by_gold_status": dict(overall_counts),
        "official_retrieval_denominator": sum(
            1 for record in io_records if official_denominator_included(record)
        ),
        "official_e2e_evaluated_count": sum(
            1
            for record in io_records
            if official_denominator_included(record)
            and record["judgement"]["verdict"] in {"pass", "fail", "partial"}
            and live_call_executed
        ),
        "track_summaries": track_summaries,
    }


def summarize_track(
    records: Sequence[Mapping[str, Any]],
    source_metrics: Mapping[str, Any],
    *,
    live_call_executed: bool,
) -> dict[str, Any]:
    counts = Counter(record.get("gold_status") for record in records)
    verdict_counts = Counter(record["judgement"]["verdict"] for record in records)
    failure_counts = Counter(
        record["judgement"]["failure_type"]
        for record in records
        if record["judgement"].get("failure_type")
    )
    official = [record for record in records if official_denominator_included(record)]
    official_evidence_hits = [
        record
        for record in official
        if record.get("retrieval", {}).get("evidence_hit") is True
    ]
    e2e_evaluated = [
        record
        for record in official
        if live_call_executed and record["judgement"]["verdict"] in {"pass", "fail", "partial"}
    ]
    pass_count = sum(1 for record in e2e_evaluated if record["judgement"]["verdict"] == "pass")
    return {
        "case_count": len(records),
        "case_counts_by_gold_status": dict(counts),
        "official_denominator_count": len(official),
        "official_retrieval_evidence_hit_rate": safe_rate(len(official_evidence_hits), len(official)),
        "source_retrieval_metrics": dict(source_metrics),
        "e2e_evaluated_gold_count": len(e2e_evaluated),
        "e2e_pass_rate": safe_rate(pass_count, len(e2e_evaluated)),
        "verdict_counts": dict(verdict_counts),
        "failure_breakdown": dict(failure_counts),
        "usage": usage_summary(records),
    }


def usage_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latencies = [float(record["usage"]["latency_ms"]) for record in records]
    input_tokens = [int(record["usage"]["input_tokens"]) for record in records]
    output_tokens = [int(record["usage"]["output_tokens"]) for record in records]
    return {
        "latency_ms_p50": percentile(latencies, 50),
        "latency_ms_p95": percentile(latencies, 95),
        "input_tokens_avg": round(statistics.mean(input_tokens), 2) if input_tokens else 0.0,
        "output_tokens_avg": round(statistics.mean(output_tokens), 2) if output_tokens else 0.0,
        "cost_usd_total": sum(
            float(record["usage"].get("cost_usd") or 0.0) for record in records
        ),
    }


def percentile(values: Sequence[float], pct: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((pct / 100) * (len(ordered) - 1))
    return round(float(ordered[index]), 2)


def safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def denominator_policy_summary() -> dict[str, Any]:
    return {
        "official_metric_gold_status": "gold",
        "excluded_statuses": ["candidate", "diagnostic_only"],
        "ambiguous_non_gold_default": "diagnostic_only",
        "codex_must_not_promote_to_gold": True,
        "report_note": (
            "Only gold cases enter official retrieval and E2E denominators. "
            "Candidate and diagnostic_only cases stay in raw I/O and failure analysis."
        ),
    }


def render_track_report(
    *,
    track: str,
    title: str,
    summary: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    source_paths: Mapping[str, str],
    representative_examples: Sequence[Mapping[str, Any]],
    known_limitations: Sequence[str],
    next_tuning_candidates: Sequence[str],
    live_call_executed: bool,
) -> str:
    track_summary = summary["track_summaries"][track]
    lines: list[str] = [
        f"# {title}",
        "",
        "## Run metadata",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Live LLM call executed: `{str(live_call_executed).lower()}`",
        f"- Capture mode note: `{capture_mode_note(live_call_executed)}`",
        "",
        "## Dataset / case counts by gold_status",
        "",
        _markdown_table(
            ["gold_status", "count"],
            [
                [status, str(count)]
                for status, count in sorted(track_summary["case_counts_by_gold_status"].items())
            ],
        ),
        "",
        "## Retrieval-only metrics",
        "",
        _metrics_table(track_summary["source_retrieval_metrics"]),
        "",
        "## E2E metrics",
        "",
        _markdown_table(
            ["metric", "value"],
            [
                ["official_denominator_count", _format_value(track_summary["official_denominator_count"])],
                ["e2e_evaluated_gold_count", _format_value(track_summary["e2e_evaluated_gold_count"])],
                ["e2e_pass_rate", _format_value(track_summary["e2e_pass_rate"])],
                ["verdict_counts", json.dumps(track_summary["verdict_counts"], ensure_ascii=False)],
            ],
        ),
        "",
        "## Answerability behavior",
        "",
        "- Gold cases require human-confirmed expected answer/evidence/answerability before official scoring.",
        "- Non-gold ambiguous cases remain `diagnostic_only` and are excluded from official denominators.",
        "",
        "## Grounding / citation support summary",
        "",
        _markdown_table(
            ["metric", "value"],
            [
                [
                    "official_retrieval_evidence_hit_rate",
                    _format_value(track_summary["official_retrieval_evidence_hit_rate"]),
                ],
                ["grounded verdict proxy", json.dumps(track_summary["verdict_counts"], ensure_ascii=False)],
                ["citation support", "not officially scored in dry-run capture"],
            ],
        ),
        "",
        "## Failure breakdown",
        "",
        _failure_table(track_summary["failure_breakdown"]),
        "",
        "## Representative examples",
        "",
        _examples_table(representative_examples),
        "",
        "## Artifact paths",
        "",
        _markdown_table(
            ["artifact", "path"],
            [[name, f"`{path}`"] for name, path in artifact_paths.items()],
        ),
        "",
        "## Source paths",
        "",
        _markdown_table(
            ["source", "path"],
            [[name, f"`{path}`"] for name, path in source_paths.items()],
        ),
        "",
        "## Known limitations",
        "",
    ]
    lines.extend([f"- {item}" for item in known_limitations])
    lines.extend(["", "## Next tuning candidates", ""])
    lines.extend([f"- {item}" for item in next_tuning_candidates])
    lines.append("")
    return "\n".join(lines)


def render_overview_report(
    *,
    summary: Mapping[str, Any],
    report_paths: Mapping[str, str],
    live_call_executed: bool,
) -> str:
    rows: list[list[str]] = []
    for track, track_summary in sorted(summary["track_summaries"].items()):
        rows.append(
            [
                track,
                _format_value(track_summary["case_count"]),
                _format_value(track_summary["official_denominator_count"]),
                _format_value(track_summary["official_retrieval_evidence_hit_rate"]),
                _format_value(track_summary["e2e_pass_rate"]),
                json.dumps(track_summary["failure_breakdown"], ensure_ascii=False),
            ]
        )
    lines = [
        "# Baseline Before Tuning Overview",
        "",
        "## Run metadata",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Live LLM call executed: `{str(live_call_executed).lower()}`",
        f"- Capture mode note: `{capture_mode_note(live_call_executed)}`",
        "",
        "## A/B/C comparison",
        "",
        _markdown_table(
            [
                "track",
                "cases",
                "official denominator",
                "retrieval evidence hit rate",
                "E2E pass rate",
                "failure breakdown",
            ],
            rows,
        ),
        "",
        "## Denominator policy",
        "",
        "- Only `gold` cases enter official retrieval metric and E2E pass-rate denominators.",
        "- `candidate` and `diagnostic_only` cases are preserved in JSONL artifacts and failure analysis only.",
        "- Expected answer/evidence/answerability policy is not promoted by Codex during this snapshot.",
        "",
        "## Report paths",
        "",
        _markdown_table(
            ["report", "path"],
            [[name, f"`{path}`"] for name, path in report_paths.items()],
        ),
        "",
    ]
    return "\n".join(lines)


def capture_mode_note(live_call_executed: bool) -> str:
    if live_call_executed:
        return "live LLM call executed with environment-based configuration"
    return "E2E I/O capture path verified, live call not executed"


def representative_examples(
    records: Sequence[Mapping[str, Any]],
    *,
    track: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    candidates = [
        record
        for record in records
        if record.get("track") == track
        and (
            record["judgement"].get("failure_type")
            or record["judgement"].get("verdict") in {"fail", "partial", "needs_human_review"}
        )
    ]
    out: list[dict[str, Any]] = []
    for record in candidates[:limit]:
        out.append(
            {
                "case_id": record.get("case_id"),
                "gold_status": record.get("gold_status"),
                "query": truncate(clean(record.get("query")), 90),
                "verdict": record["judgement"].get("verdict"),
                "failure_type": record["judgement"].get("failure_type"),
                "notes": truncate(clean(record["judgement"].get("notes")), 120),
            }
        )
    return out


def _examples_table(examples: Sequence[Mapping[str, Any]]) -> str:
    if not examples:
        return "_No representative failures selected._"
    return _markdown_table(
        ["case_id", "gold_status", "query", "verdict", "failure_type", "notes"],
        [
            [
                clean(example.get("case_id")),
                clean(example.get("gold_status")),
                clean(example.get("query")),
                clean(example.get("verdict")),
                clean(example.get("failure_type")),
                clean(example.get("notes")),
            ]
            for example in examples
        ],
    )


def _failure_table(failure_breakdown: Mapping[str, Any]) -> str:
    if not failure_breakdown:
        return "_No automatic failure types were counted._"
    return _markdown_table(
        ["failure_type", "count"],
        [[key, str(value)] for key, value in sorted(failure_breakdown.items())],
    )


def _metrics_table(metrics: Mapping[str, Any]) -> str:
    if not metrics:
        return "_No source retrieval metrics were available for this track._"
    priority_keys = [
        "Hit@1",
        "Hit@3",
        "Hit@5",
        "Hit@10",
        "MRR@10",
        "source_recall@10",
        "chunk_recall@10",
        "xlsx_citation_location_accuracy",
        "pdf_citation_location_accuracy",
        "candidate_namespace_chunk_count",
        "c5_ready",
    ]
    rows = []
    for key in priority_keys:
        if key in metrics:
            rows.append([key, _format_value(metrics[key])])
    for key, value in sorted(metrics.items()):
        if key not in priority_keys and len(rows) < 14:
            rows.append([key, _format_value(value)])
    return _markdown_table(["metric", "value"], rows)


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_escape_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()
