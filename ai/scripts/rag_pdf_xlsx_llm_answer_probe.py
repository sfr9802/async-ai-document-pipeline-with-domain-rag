"""Run a diagnostic-only XLSX LLM answer-output probe.

This sidecar keeps answer generation and gold-intent inspection separated:

* answer prompts are built only from query text, selected evidence, compiled
  deterministic drafts, and locators
* expected/must/gold fields are read only by the separate gold-intent role probe
* official answer denominators and promotion evidence remain zero/false
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
EVAL_RUNS_DIR = AI_WORKER_ROOT / "eval" / "artifacts" / "eval_runs"

if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_pdf_xlsx_local_llm_answer_runner import (  # noqa: E402
    call_local_llm,
    entry_blockers,
    resolve_base_url,
)


INPUT_SCHEMA_VERSION = "rag_pdf_xlsx_llm_answer_probe_inputs_v1"
OUTPUT_SCHEMA_VERSION = "rag_pdf_xlsx_llm_answer_probe_outputs_v1"
ROLE_SCHEMA_VERSION = "rag_pdf_xlsx_gold_intent_role_probe_v1"
REPORT_SCHEMA_VERSION = "rag_pdf_xlsx_llm_answer_probe_report_v1"
PROMPT_VERSION = "xlsx_answer_probe_prompt_v1"
RUN_PREFIX = "pdf_xlsx_answer_shape_xlsx_llm_answer_probe"

BANNED_ANSWER_PROMPT_KEYS = {
    "expected_answer_text",
    "must_contain_terms",
    "expected_evidence_location",
    "expected_current_evidence_location",
    "expected_evidence_locator",
    "expected_evidence_locator_diagnostic_only",
    "expected_answer",
    "expected_sheet",
    "expected_range",
    "expected_cell",
    "gold_answer",
    "gold_evidence",
    "gold_label",
    "gold_field",
    "gold_decision",
    "gold_policy",
    "relevance_label",
    "answerability_label",
    "label_relevance",
    "label_answerability",
    "label_status",
    "denominator_policy",
    "official_denominator",
    "promotion_denominator",
    "user_gold_decision",
    "suggested_gold_decision",
}

ANSWER_TYPES = {
    "CELL_VALUE",
    "ROW_SUMMARY",
    "RANGE_SUMMARY",
    "LOCATION_PLUS_CONTENT",
    "ABSTAIN",
}

ROLE_FIELDNAMES = [
    "query_id",
    "expected_answer_text_role",
    "must_contain_terms_roles_json",
    "does_expected_answer_text_look_like_final_answer",
    "does_must_contain_include_actual_value",
    "does_must_contain_look_keyword_only",
    "human_review_required",
    "rationale",
]

REPORT_FIELDNAMES = [
    "query_id",
    "trace_id",
    "track",
    "eval_mode",
    "answer_allowed",
    "fail_closed_reason",
    "llm_smoke_status",
    "raw_output_status",
    "parser_status",
    "content_shape_status",
    "citation_validation_status",
    "official_metric_included",
    "answer_generation_denominator_included",
    "failure_reason",
    "prompt_hash",
    "context_hash",
    "answer_type",
    "answer",
    "abstain_reason",
    "parse_ok",
    "unsupported_claim_count",
    "gold_leakage_suspected",
    "citation_missing",
    "citation_not_in_context",
    "citation_support_status",
    "citation_failure_reasons",
    "locator_only_answer",
    "keyword_echo_only",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_probe(
        source_artifact_dir=Path(args.source_artifact_dir) if args.source_artifact_dir else None,
        inputs_path=Path(args.inputs) if args.inputs else None,
        evidence_objects_path=Path(args.evidence_objects) if args.evidence_objects else None,
        compiled_answers_path=Path(args.compiled_answers) if args.compiled_answers else None,
        output_root=Path(args.output_root),
        run_id=args.run_id,
        run_prefix=args.run_prefix,
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
        max_rows=args.max_rows,
    )
    print_json(
        {
            "status": report["status"],
            "artifact_dir": report["artifact_dir"],
            "model": report["llm_model"],
            "backend": report["llm_backend"],
            "local_llm_run": report["local_llm_run"],
            "external_live_llm_run": report["external_live_llm_run"],
            "llm_answer_count": report["llm_answer_count"],
            "llm_abstain_count": report["llm_abstain_count"],
            "llm_invalid_json_count": report["llm_invalid_json_count"],
            "promotion_evidence": report["promotion_evidence"],
            "official_xlsx_answer_eval_denominator": report["official_xlsx_answer_eval_denominator"],
        }
    )
    if report["status"] == "PASS":
        return 0
    if args.allow_diagnostic_failures and report["status"] == "PASS_WITH_WARNINGS":
        return 0
    return 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-artifact-dir", default="", help="Directory containing answer/evidence/compiled JSONL")
    parser.add_argument("--inputs", default="", help="answer_generation_inputs.jsonl")
    parser.add_argument("--evidence-objects", default="", help="evidence_objects.jsonl")
    parser.add_argument("--compiled-answers", default="", help="compiled_answers.jsonl")
    parser.add_argument("--output-root", default=str(EVAL_RUNS_DIR))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-prefix", default=RUN_PREFIX)
    parser.add_argument(
        "--backend",
        choices=["llamacpp", "ollama"],
        default=os.environ.get("PDF_XLSX_LOCAL_LLM_BACKEND", "llamacpp"),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PDF_XLSX_LOCAL_LLM_BASE_URL", ""),
        help="Local backend URL. External/cloud endpoints are rejected.",
    )
    parser.add_argument("--model", default=os.environ.get("PDF_XLSX_LLM_ANSWER_PROBE_MODEL", "gemma4-e2b-local"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--max-rows", type=int, default=0, help="0 means all XLSX rows")
    parser.add_argument(
        "--allow-diagnostic-failures",
        action="store_true",
        help="Return 0 for schema-valid diagnostic failures; official metrics still remain excluded.",
    )
    return parser.parse_args(argv)


def run_probe(
    *,
    source_artifact_dir: Path | None,
    inputs_path: Path | None,
    evidence_objects_path: Path | None,
    compiled_answers_path: Path | None,
    output_root: Path,
    run_id: str,
    run_prefix: str,
    backend: str,
    base_url: str,
    model: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
    max_rows: int = 0,
    llm_client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    run_id = run_id or utc_run_id()
    generated_at = utc_timestamp()
    source_artifact_dir = source_artifact_dir or find_latest_source_artifact(EVAL_RUNS_DIR)
    inputs_path = inputs_path or source_artifact_dir / "answer_generation_inputs.jsonl"
    evidence_objects_path = evidence_objects_path or source_artifact_dir / "evidence_objects.jsonl"
    compiled_answers_path = compiled_answers_path or source_artifact_dir / "compiled_answers.jsonl"
    artifact_dir = output_root / f"{run_prefix}_{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    source_rows = read_jsonl(inputs_path)
    evidence_rows = [row for row in read_jsonl(evidence_objects_path) if clean(row.get("track")).upper() == "XLSX"]
    compiled_rows = [row for row in read_jsonl(compiled_answers_path) if clean(row.get("track")).upper() == "XLSX"]
    if max_rows > 0:
        evidence_rows = evidence_rows[:max_rows]
    source_by_id = keyed_by_query_id(source_rows)
    compiled_by_id = keyed_by_query_id(compiled_rows)

    probe_input_rows = [
        build_llm_answer_probe_input_row(
            evidence_row=evidence_row,
            compiled_row=compiled_by_id.get(clean(evidence_row.get("query_id")), {}),
            run_id=run_id,
        )
        for evidence_row in evidence_rows
    ]
    input_errors = answer_prompt_leakage_errors(probe_input_rows, source_by_id)
    if input_errors:
        probe_input_rows = [
            fail_closed_probe_input_row(row, reason="ANSWER_PROMPT_LEAKAGE_GUARD")
            for row in probe_input_rows
        ]

    llm_inputs_path = artifact_dir / "llm_answer_probe_inputs.jsonl"
    outputs_path = artifact_dir / "llm_answer_probe_outputs.jsonl"
    role_jsonl_path = artifact_dir / "gold_intent_role_probe.jsonl"
    role_csv_path = artifact_dir / "gold_intent_role_probe.csv"
    report_path = artifact_dir / "llm_answer_probe_report.json"
    report_csv_path = artifact_dir / "llm_answer_probe_report.csv"
    manifest_path = artifact_dir / "manifest.json"

    write_jsonl(llm_inputs_path, probe_input_rows)

    answer_outputs, llm_meta = run_llm_answer_outputs(
        probe_input_rows=probe_input_rows,
        inputs_path=llm_inputs_path,
        source_by_id=source_by_id,
        model=model,
        backend=backend,
        base_url=base_url,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        llm_client=llm_client,
    )
    write_jsonl(outputs_path, answer_outputs)

    role_rows = [
        build_gold_intent_role_row(
            source_row=source_by_id.get(clean(probe_input.get("query_id")), {}),
            probe_input=probe_input,
            answer_output=keyed_by_query_id(answer_outputs).get(clean(probe_input.get("query_id")), {}),
        )
        for probe_input in probe_input_rows
    ]
    write_jsonl(role_jsonl_path, role_rows)
    write_csv(role_csv_path, ROLE_FIELDNAMES, role_csv_rows(role_rows))

    metrics = metrics_from_outputs(
        probe_input_rows=probe_input_rows,
        answer_outputs=answer_outputs,
        role_rows=role_rows,
        input_errors=input_errors,
    )
    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        source_artifact_dir=source_artifact_dir,
        inputs_path=inputs_path,
        evidence_objects_path=evidence_objects_path,
        compiled_answers_path=compiled_answers_path,
        artifact_dir=artifact_dir,
        llm_inputs_path=llm_inputs_path,
        outputs_path=outputs_path,
        role_jsonl_path=role_jsonl_path,
        role_csv_path=role_csv_path,
        report_path=report_path,
        report_csv_path=report_csv_path,
        manifest_path=manifest_path,
        model=model,
        backend=backend,
        base_url=llm_meta["base_url"],
        generated_metrics=metrics,
        llm_meta=llm_meta,
        input_errors=input_errors,
    )
    write_json(report_path, report)
    write_csv(report_csv_path, REPORT_FIELDNAMES, report_csv_rows(answer_outputs))

    manifest = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": report["status"],
        "artifact_dir": repo_relative(artifact_dir),
        "manifest_path": repo_relative(manifest_path),
        "llm_answer_probe_inputs": artifact_entry(llm_inputs_path),
        "llm_answer_probe_outputs": artifact_entry(outputs_path),
        "gold_intent_role_probe_jsonl": artifact_entry(role_jsonl_path),
        "gold_intent_role_probe_csv": artifact_entry(role_csv_path),
        "report_json": artifact_entry(report_path),
        "report_csv": artifact_entry(report_csv_path),
        "source_inputs": report["source_inputs"],
        "llm_model": model,
        "llm_backend": backend,
        "llm_base_url": llm_meta["base_url"],
        "local_llm_run": llm_meta["local_llm_run"],
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "prompt_version": PROMPT_VERSION,
        "promotion_evidence": False,
        "official_xlsx_answer_eval_denominator": 0,
        "gold_intent_probe_used_for_scoring": False,
        "expected_answer_text_used_in_answer_prompt": False,
        "must_contain_terms_used_in_answer_prompt": False,
        "expected_evidence_location_used_in_answer_prompt": False,
        "guardrails": diagnostic_guardrails(),
        **metrics,
    }
    write_json(manifest_path, manifest)
    return report


def build_llm_answer_probe_input_row(
    *,
    evidence_row: Mapping[str, Any],
    compiled_row: Mapping[str, Any],
    run_id: str,
) -> dict[str, Any]:
    query_id = clean(evidence_row.get("query_id"))
    evidence_object = evidence_row.get("evidence_object") if isinstance(evidence_row.get("evidence_object"), Mapping) else {}
    compiled_answer = (
        compiled_row.get("compiled_answer")
        if isinstance(compiled_row.get("compiled_answer"), Mapping)
        else compiled_row.get("compiled_answer_draft")
        if isinstance(compiled_row.get("compiled_answer_draft"), Mapping)
        else {}
    )
    answer_allowed = parse_bool(evidence_row.get("answer_allowed")) or parse_bool(
        evidence_row.get("answer_generation_allowed")
    )
    fail_closed_reason = clean(
        evidence_row.get("fail_closed_reason")
        or evidence_row.get("answer_disallowed_reason")
        or evidence_row.get("answer_generation_blocker")
    )
    policy_pending = (
        parse_bool(evidence_row.get("policy_pending"))
        or "POLICY_PENDING" in fail_closed_reason.upper()
        or clean(evidence_row.get("expected_answer_shape")).upper() == "NOT_ANSWERABLE_OR_POLICY_PENDING"
    )
    if policy_pending:
        answer_allowed = False
        fail_closed_reason = fail_closed_reason or "XLSX_POLICY_PENDING"
    prompt_payload: dict[str, Any] | None = None
    prompt_text = ""
    if answer_allowed:
        prompt_payload = build_answer_prompt_payload(
            query=clean(evidence_row.get("query")),
            evidence_object=evidence_object,
            compiled_answer=compiled_answer,
            content_source_fields=string_list(evidence_row.get("content_source_fields")),
        )
        prompt_text = build_answer_prompt_text(query_id=query_id, expected_shape=clean(evidence_row.get("expected_answer_shape")), payload=prompt_payload)
    return {
        "schema_version": INPUT_SCHEMA_VERSION,
        "run_id": run_id,
        "source_evidence_run_id": clean(evidence_row.get("run_id")),
        "row_index": evidence_row.get("row_index"),
        "query_id": query_id,
        "track": "XLSX",
        "query": clean(evidence_row.get("query")),
        "expected_answer_shape": clean(evidence_row.get("expected_answer_shape")),
        "answer_allowed": answer_allowed,
        "answer_generation_allowed": answer_allowed,
        "fail_closed_reason": fail_closed_reason,
        "llm_requested": answer_allowed,
        "llm_skipped_reason": "" if answer_allowed else (fail_closed_reason or "answer_generation_not_allowed"),
        "prompt_version": PROMPT_VERSION,
        "answer_prompt_payload": prompt_payload or {},
        "answer_prompt_payload_sha256": stable_sha256(prompt_payload or {}),
        "answer_prompt": prompt_text,
        "answer_prompt_sha256": stable_sha256(prompt_text),
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }


def fail_closed_probe_input_row(row: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    clean_row = dict(row)
    clean_row["answer_allowed"] = False
    clean_row["answer_generation_allowed"] = False
    clean_row["fail_closed_reason"] = reason
    clean_row["llm_requested"] = False
    clean_row["llm_skipped_reason"] = reason
    clean_row["answer_prompt_payload"] = {}
    clean_row["answer_prompt"] = ""
    return clean_row


def build_answer_prompt_payload(
    *,
    query: str,
    evidence_object: Mapping[str, Any],
    compiled_answer: Mapping[str, Any],
    content_source_fields: list[str],
) -> dict[str, Any]:
    locator = xlsx_locator(evidence_object)
    selected = {
        "content_source_fields": content_source_fields,
        "selected_search_unit_id": clean(evidence_object.get("selected_search_unit_id")),
        "selected_searchunit_locator": safe_citation_locator(evidence_object.get("selected_searchunit_locator")),
        "content_source_locator": safe_citation_locator(evidence_object.get("content_source_locator")),
        "content_summary": clean(evidence_object.get("content_summary")),
        "row_label": clean(evidence_object.get("row_label")),
        "column_label": clean(evidence_object.get("column_label")),
        "value": clean(evidence_object.get("value")),
        "header_context": string_list(evidence_object.get("header_context"))[:12],
        "row_values": mapping_list(evidence_object.get("row_values"))[:12],
        "column_values": mapping_list(evidence_object.get("column_values"))[:12],
        "cell_values": mapping_list(evidence_object.get("cell_values"))[:12],
        "nearby_rows": string_list(evidence_object.get("nearby_rows"))[:8],
        "table_context": string_list(evidence_object.get("table_context"))[:8],
        "query_binding": safe_query_binding(evidence_object.get("query_binding")),
    }
    return {
        "task": "diagnostic_xlsx_answer_probe",
        "query": query,
        "evidence": compact_mapping(
            {
                "evidence_type": "xlsx",
                "file_name": clean(evidence_object.get("file_name")),
                "sheet": clean(evidence_object.get("sheet")),
                "range": clean(evidence_object.get("range")),
                "cell": clean(evidence_object.get("cell")),
                "locator": locator,
                **selected,
            }
        ),
        "compiled_deterministic_draft": safe_compiled_answer(compiled_answer),
        "selected_searchunit_content_fields": compact_mapping(selected),
        "citation_locator": safe_citation_locator(evidence_object.get("citation_locator")) or locator,
        "sheet_range_cell_locator": locator,
    }


def safe_compiled_answer(value: Mapping[str, Any]) -> dict[str, Any]:
    citations = value.get("citations") if isinstance(value.get("citations"), list) else []
    return compact_mapping(
        {
            "answer": clean(value.get("answer")),
            "answer_shape": clean(value.get("answer_shape")),
            "answer_type": clean(value.get("answer_type")),
            "citations": [
                {
                    "claim": clean(citation.get("claim")),
                    "locator": safe_citation_locator(citation.get("locator")),
                    "supports_claim": parse_bool(citation.get("supports_claim")),
                }
                for citation in citations
                if isinstance(citation, Mapping)
            ],
            "abstain_reason": clean(value.get("abstain_reason")),
            "used_content_terms": string_list(value.get("used_content_terms")),
            "failure_mode_if_any": clean(value.get("failure_mode_if_any")),
        }
    )


def safe_citation_locator(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return compact_mapping(
        {
            "file": clean(value.get("file")),
            "sheet": clean(value.get("sheet")),
            "range": clean(value.get("range")),
            "cell": clean(value.get("cell")),
            "search_unit_id": clean(value.get("search_unit_id")),
            "document_version_id": clean(value.get("document_version_id")),
        }
    )


def build_answer_prompt_text(*, query_id: str, expected_shape: str, payload: Mapping[str, Any]) -> str:
    return f"""You are running a diagnostic-only XLSX answer-output probe.

Return exactly one JSON object and no markdown:
{{
  "query_id": "{json_escape(query_id)}",
  "answer": "...",
  "answer_type": "CELL_VALUE|ROW_SUMMARY|RANGE_SUMMARY|LOCATION_PLUS_CONTENT|ABSTAIN",
  "citations": [
    {{"file": "...", "sheet": "...", "range": "...", "source": "selected_searchunit_payload", "search_unit_id": "...", "document_version_id": "..."}}
  ],
  "used_evidence_fields": [],
  "unsupported_claims": [],
  "abstain_reason": "",
  "confidence": "low|medium|high"
}}

Rules:
- Answer only from supplied evidence, compiled deterministic draft, and selected SearchUnit content fields.
- Include a citation for every content claim.
- If citation locators include file, search_unit_id, or document_version_id, copy those identity fields exactly.
- Do not add claims not present in supplied evidence.
- If evidence is insufficient, set answer_type to ABSTAIN, answer to "", citations to [], and fill abstain_reason.
- Do not mention or infer any expected answer, must-contain term, gold evidence, relevance label, answerability label, or user gold decision.
- Use answer_type compatible with the evidence and expected shape {expected_shape}.

Diagnostic input:
{json.dumps(payload, ensure_ascii=False, sort_keys=True)}
"""


def run_llm_answer_outputs(
    *,
    probe_input_rows: list[dict[str, Any]],
    inputs_path: Path,
    source_by_id: Mapping[str, Mapping[str, Any]],
    model: str,
    backend: str,
    base_url: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
    llm_client: Callable[[str], str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_url = resolve_base_url(backend, base_url)
    requested_rows = [row for row in probe_input_rows if parse_bool(row.get("llm_requested"))]
    blockers = []
    if requested_rows and llm_client is None:
        blockers = entry_blockers(
            inputs_path=inputs_path,
            rows=requested_rows,
            model=model,
            backend=backend,
            base_url=base_url,
        )
    outputs: list[dict[str, Any]] = []
    if blockers:
        for row in probe_input_rows:
            outputs.append(
                output_row_from_abstain(
                    probe_input=row,
                    reason=";".join(blockers),
                    model=model,
                    backend=backend,
                    base_url=base_url,
                    parse_ok=True,
                    llm_requested=parse_bool(row.get("llm_requested")),
                    local_llm_run=False,
                )
            )
        return outputs, {
            "base_url": base_url,
            "blockers": blockers,
            "local_llm_run": False,
            "llm_requested_count": len(requested_rows),
        }

    local_llm_run = False
    for row in probe_input_rows:
        if not parse_bool(row.get("llm_requested")):
            outputs.append(
                output_row_from_abstain(
                    probe_input=row,
                    reason=clean(row.get("fail_closed_reason")) or "answer_generation_not_allowed",
                    model=model,
                    backend=backend,
                    base_url=base_url,
                    parse_ok=True,
                    llm_requested=False,
                    local_llm_run=False,
                )
            )
            continue
        raw = ""
        llm_error = ""
        parsed: dict[str, Any] = {}
        parse_ok = False
        try:
            raw = llm_client(clean(row.get("answer_prompt"))) if llm_client else call_local_llm(
                backend=backend,
                base_url=base_url,
                model=model,
                prompt=clean(row.get("answer_prompt")),
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            parsed, parse_ok = parse_probe_answer_json(raw, fallback_query_id=clean(row.get("query_id")))
            local_llm_run = llm_client is None or local_llm_run
        except Exception as exc:  # keep later rows diagnosable
            llm_error = f"{type(exc).__name__}: {exc}"
            parsed = abstain_probe_answer(clean(row.get("query_id")), llm_error)
            parse_ok = False
        outputs.append(
            output_row_from_llm(
                probe_input=row,
                parsed_answer=parsed,
                raw_answer=raw,
                parse_ok=parse_ok,
                llm_error=llm_error,
                source_row=source_by_id.get(clean(row.get("query_id")), {}),
                model=model,
                backend=backend,
                base_url=base_url,
            )
        )
    return outputs, {
        "base_url": base_url,
        "blockers": [],
        "local_llm_run": local_llm_run,
        "llm_requested_count": len(requested_rows),
    }


def output_row_from_llm(
    *,
    probe_input: Mapping[str, Any],
    parsed_answer: Mapping[str, Any],
    raw_answer: str,
    parse_ok: bool,
    llm_error: str,
    source_row: Mapping[str, Any],
    model: str,
    backend: str,
    base_url: str,
) -> dict[str, Any]:
    normalized = normalize_probe_answer(parsed_answer, fallback_query_id=clean(probe_input.get("query_id")))
    checks = answer_checks(probe_input=probe_input, parsed_answer=normalized, source_row=source_row)
    diagnostic_fields = llm_diagnostic_status_fields(
        probe_input=probe_input,
        parsed_answer=normalized,
        parse_ok=parse_ok and is_probe_answer_schema(normalized),
        checks=checks,
        raw_answer=raw_answer,
        llm_error=llm_error,
    )
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "run_id": clean(probe_input.get("run_id")),
        "trace_id": diagnostic_fields["trace_id"],
        "query_id": clean(probe_input.get("query_id")),
        "track": "XLSX",
        "eval_mode": "diagnostic",
        "query": clean(probe_input.get("query")),
        "expected_answer_shape": clean(probe_input.get("expected_answer_shape")),
        "answer_allowed": parse_bool(probe_input.get("answer_allowed")),
        "answer_generation_allowed": parse_bool(probe_input.get("answer_generation_allowed")),
        "fail_closed_reason": clean(probe_input.get("fail_closed_reason")),
        "answer_json_raw": raw_answer,
        "parsed_answer": normalized,
        "parse_ok": diagnostic_fields["parser_status"] == "RAW_JSON_VALID",
        "llm_requested": parse_bool(probe_input.get("llm_requested")),
        "llm_error": llm_error,
        "local_llm_run": True,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "diagnostic_generation_only": True,
        "official_scoring_allowed": False,
        "official_metric_included": False,
        "answer_generation_denominator_included": False,
        "gold_intent_probe_used_for_scoring": False,
        "llm_model": model,
        "llm_backend": backend,
        "llm_base_url": base_url,
        "prompt_version": PROMPT_VERSION,
        "answer": normalized["answer"],
        "answer_type": normalized["answer_type"],
        "citations": normalized["citations"],
        "used_evidence_fields": normalized["used_evidence_fields"],
        "unsupported_claims": checks["unsupported_claims"],
        "abstain_reason": normalized["abstain_reason"],
        "confidence": normalized["confidence"],
        **diagnostic_fields,
        **checks,
    }


def output_row_from_abstain(
    *,
    probe_input: Mapping[str, Any],
    reason: str,
    model: str,
    backend: str,
    base_url: str,
    parse_ok: bool,
    llm_requested: bool,
    local_llm_run: bool,
) -> dict[str, Any]:
    parsed = abstain_probe_answer(clean(probe_input.get("query_id")), reason)
    diagnostic_fields = llm_diagnostic_status_fields(
        probe_input=probe_input,
        parsed_answer=parsed,
        parse_ok=parse_ok,
        checks={
            "llm_unsupported_claim_count": 0,
            "llm_gold_leakage_suspected": False,
            "llm_citation_missing": False,
            "llm_citation_not_in_context": False,
            "llm_locator_only_answer": False,
            "llm_keyword_echo_only": False,
        },
        raw_answer=json.dumps(parsed, ensure_ascii=False, sort_keys=True),
        llm_error="",
    )
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "run_id": clean(probe_input.get("run_id")),
        "trace_id": diagnostic_fields["trace_id"],
        "query_id": clean(probe_input.get("query_id")),
        "track": "XLSX",
        "eval_mode": "diagnostic",
        "query": clean(probe_input.get("query")),
        "expected_answer_shape": clean(probe_input.get("expected_answer_shape")),
        "answer_allowed": parse_bool(probe_input.get("answer_allowed")),
        "answer_generation_allowed": parse_bool(probe_input.get("answer_generation_allowed")),
        "fail_closed_reason": clean(probe_input.get("fail_closed_reason")),
        "answer_json_raw": json.dumps(parsed, ensure_ascii=False, sort_keys=True),
        "parsed_answer": parsed,
        "parse_ok": parse_ok,
        "llm_requested": llm_requested,
        "llm_error": "",
        "local_llm_run": local_llm_run,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "diagnostic_generation_only": True,
        "official_scoring_allowed": False,
        "official_metric_included": False,
        "answer_generation_denominator_included": False,
        "gold_intent_probe_used_for_scoring": False,
        "llm_model": model,
        "llm_backend": backend,
        "llm_base_url": base_url,
        "prompt_version": PROMPT_VERSION,
        "answer": "",
        "answer_type": "ABSTAIN",
        "citations": [],
        "used_evidence_fields": [],
        "unsupported_claims": [],
        "abstain_reason": reason,
        "confidence": "low",
        "llm_unsupported_claim_count": 0,
        "llm_gold_leakage_suspected": False,
        "llm_citation_missing": False,
        "llm_citation_not_in_context": False,
        "llm_citation_support_status": "NOT_APPLICABLE",
        "llm_citation_failure_reasons": [],
        "llm_locator_only_answer": False,
        "llm_keyword_echo_only": False,
        **diagnostic_fields,
    }


def llm_diagnostic_status_fields(
    *,
    probe_input: Mapping[str, Any],
    parsed_answer: Mapping[str, Any],
    parse_ok: bool,
    checks: Mapping[str, Any],
    raw_answer: str,
    llm_error: str,
) -> dict[str, Any]:
    query_id = clean(probe_input.get("query_id"))
    run_id = clean(probe_input.get("run_id"))
    answer = clean(parsed_answer.get("answer"))
    keyword_only = parse_bool(checks.get("llm_keyword_echo_only"))
    locator_only = parse_bool(checks.get("llm_locator_only_answer"))
    citation_missing = parse_bool(checks.get("llm_citation_missing"))
    citation_not_in_context = parse_bool(checks.get("llm_citation_not_in_context"))
    unsupported = int_or_zero(checks.get("llm_unsupported_claim_count")) > 0
    gold_leakage = parse_bool(checks.get("llm_gold_leakage_suspected"))
    raw_output_status = "RAW_JSON_VALID" if parse_ok else "MODEL_OUTPUT_INVALID_JSON"
    parser_status = "RAW_JSON_VALID" if parse_ok else "JSON_REPAIR_FAILED"
    if keyword_only or locator_only:
        content_shape_status = "KEYWORD_ONLY_REJECTED"
    elif not parse_ok or not answer:
        content_shape_status = "DIAGNOSTIC_FAILURE"
    else:
        content_shape_status = "GROUNDED_DIAGNOSTIC_PASS"
    if citation_missing:
        citation_validation_status = "CITATION_MISSING"
    elif citation_not_in_context:
        citation_validation_status = "CITATION_NOT_IN_CONTEXT"
    elif parse_ok and answer:
        citation_validation_status = "GROUNDED_DIAGNOSTIC_PASS"
    else:
        citation_validation_status = "DIAGNOSTIC_FAILURE"

    failure_reason = ""
    if not parse_ok:
        failure_reason = "MODEL_OUTPUT_INVALID_JSON" if raw_answer or not llm_error else "DIAGNOSTIC_FAILURE"
    elif keyword_only or locator_only:
        failure_reason = "KEYWORD_ONLY_REJECTED"
    elif citation_missing:
        failure_reason = "CITATION_MISSING"
    elif citation_not_in_context:
        failure_reason = "CITATION_NOT_IN_CONTEXT"
    elif unsupported:
        failure_reason = "UNSUPPORTED_ANSWER"
    elif gold_leakage:
        failure_reason = "GOLD_LEAKAGE_SUSPECTED"
    elif not answer:
        failure_reason = clean(parsed_answer.get("abstain_reason")) or clean(probe_input.get("fail_closed_reason")) or "DIAGNOSTIC_FAILURE"

    passed = (
        parse_ok
        and bool(answer)
        and not any([keyword_only, locator_only, citation_missing, citation_not_in_context, unsupported, gold_leakage])
    )
    return {
        "trace_id": f"{run_id}:{query_id}:llm_smoke",
        "eval_mode": "diagnostic",
        "llm_smoke_status": "GROUNDED_DIAGNOSTIC_PASS" if passed else "DIAGNOSTIC_FAILURE",
        "raw_output_status": raw_output_status,
        "parser_status": parser_status,
        "content_shape_status": content_shape_status,
        "citation_validation_status": citation_validation_status,
        "official_metric_included": False,
        "answer_generation_denominator_included": False,
        "failure_reason": failure_reason,
        "prompt_hash": clean(probe_input.get("answer_prompt_sha256")),
        "context_hash": clean(probe_input.get("answer_prompt_payload_sha256")),
        "raw_output_present": bool(clean(raw_answer)),
    }


def answer_checks(
    *,
    probe_input: Mapping[str, Any],
    parsed_answer: Mapping[str, Any],
    source_row: Mapping[str, Any],
) -> dict[str, Any]:
    answer = clean(parsed_answer.get("answer"))
    prompt_payload = probe_input.get("answer_prompt_payload") if isinstance(probe_input.get("answer_prompt_payload"), Mapping) else {}
    if not answer:
        return {
            "llm_unsupported_claim_count": 0,
            "llm_gold_leakage_suspected": False,
            "llm_citation_missing": False,
            "llm_citation_not_in_context": False,
            "llm_citation_support_status": "NOT_APPLICABLE",
            "llm_citation_failure_reasons": [],
            "llm_locator_only_answer": False,
            "llm_keyword_echo_only": False,
            "unsupported_claims": [],
        }
    evidence_text = flatten_text(prompt_payload)
    unsupported = []
    if not text_supported_by(answer, evidence_text):
        unsupported.append(answer)
    leaked_terms = gold_terms_only_in_answer(answer=answer, evidence_text=evidence_text, source_row=source_row)
    citations = parsed_answer.get("citations") if isinstance(parsed_answer.get("citations"), list) else []
    citation_missing = not citations or any(not valid_probe_citation(citation) for citation in citations)
    citation_support = validate_probe_citations(citations, prompt_payload)
    locator_only = looks_like_locator_only_answer(answer, probe_input)
    keyword_echo = looks_like_keyword_echo_only(answer, clean(probe_input.get("query")), source_row)
    return {
        "llm_unsupported_claim_count": len(unsupported),
        "llm_gold_leakage_suspected": bool(leaked_terms),
        "llm_citation_missing": citation_missing,
        "llm_citation_not_in_context": citation_support["unsupported_count"] > 0,
        "llm_citation_support_status": citation_support["status"],
        "llm_citation_failure_reasons": citation_support["failure_reasons"],
        "llm_locator_only_answer": locator_only,
        "llm_keyword_echo_only": keyword_echo,
        "unsupported_claims": unsupported,
        "gold_leakage_terms": leaked_terms,
    }


def build_gold_intent_role_row(
    *,
    source_row: Mapping[str, Any],
    probe_input: Mapping[str, Any],
    answer_output: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_summary = evidence_summary_for_role_probe(probe_input)
    expected_text = clean(source_row.get("expected_answer_text"))
    must_terms = string_list(source_row.get("must_contain_terms"))
    expected_role = classify_expected_answer_text_role(
        expected_text=expected_text,
        query=clean(source_row.get("query")) or clean(probe_input.get("query")),
        expected_shape=clean(source_row.get("expected_answer_shape")) or clean(probe_input.get("expected_answer_shape")),
        llm_answer=clean(answer_output.get("answer")),
        deterministic_answer=clean(nested(probe_input, "answer_prompt_payload", "compiled_deterministic_draft", "answer")),
        evidence_summary=evidence_summary,
        fail_closed_reason=clean(probe_input.get("fail_closed_reason")),
    )
    term_roles = [
        {
            "term": term,
            "role": classify_must_contain_term_role(
                term=term,
                query=clean(source_row.get("query")) or clean(probe_input.get("query")),
                evidence_summary=evidence_summary,
                fail_closed_reason=clean(probe_input.get("fail_closed_reason")),
            ),
        }
        for term in must_terms
    ]
    expected_final = expected_role == "EXACT_ANSWER_VALUE"
    must_has_value = any(item["role"] == "REQUIRED_TARGET_VALUE" for item in term_roles)
    must_keyword_only = bool(term_roles) and all(
        item["role"] in {"KEYWORD_ONLY", "REQUIRED_ENTITY_ANCHOR", "REQUIRED_HEADER_ANCHOR"}
        for item in term_roles
    )
    ambiguous = expected_role == "AMBIGUOUS_NEEDS_HUMAN_REVIEW" or any(
        item["role"] == "AMBIGUOUS_NEEDS_HUMAN_REVIEW" for item in term_roles
    )
    placeholder = expected_role == "POLICY_OR_REVIEW_PLACEHOLDER" or any(
        item["role"] == "POLICY_GUARDRAIL_TERM" for item in term_roles
    )
    row = {
        "schema_version": ROLE_SCHEMA_VERSION,
        "run_id": clean(probe_input.get("run_id")),
        "query_id": clean(probe_input.get("query_id")),
        "query": clean(source_row.get("query")) or clean(probe_input.get("query")),
        "expected_answer_shape": clean(source_row.get("expected_answer_shape")) or clean(probe_input.get("expected_answer_shape")),
        "expected_answer_text_role": expected_role,
        "must_contain_terms_roles": term_roles,
        "does_expected_answer_text_look_like_final_answer": expected_final,
        "does_must_contain_include_actual_value": must_has_value,
        "does_must_contain_look_keyword_only": must_keyword_only,
        "human_review_required": ambiguous or placeholder or (expected_final and must_keyword_only),
        "rationale": role_rationale(expected_role, term_roles, expected_final, must_has_value, must_keyword_only),
        "gold_intent_probe_used_for_scoring": False,
        "answer_evidence_updated": False,
        "promotion_evidence": False,
    }
    return row


def classify_expected_answer_text_role(
    *,
    expected_text: str,
    query: str,
    expected_shape: str,
    llm_answer: str,
    deterministic_answer: str,
    evidence_summary: Mapping[str, Any],
    fail_closed_reason: str,
) -> str:
    if not expected_text:
        return "POLICY_OR_REVIEW_PLACEHOLDER" if fail_closed_reason else "AMBIGUOUS_NEEDS_HUMAN_REVIEW"
    if looks_like_policy_placeholder(expected_text) or "POLICY_PENDING" in fail_closed_reason:
        return "POLICY_OR_REVIEW_PLACEHOLDER"
    if looks_like_locator_text(expected_text):
        return "RANGE_OR_LOCATION_LABEL"
    if term_in_any(expected_text, evidence_summary.get("headers")):
        return "HEADER_OR_COLUMN_ANCHOR"
    if term_in_any(expected_text, evidence_summary.get("locations")):
        return "RANGE_OR_LOCATION_LABEL"
    if final_answer_like(expected_text, llm_answer, deterministic_answer, evidence_summary):
        return "EXACT_ANSWER_VALUE"
    if term_in_any(expected_text, evidence_summary.get("row_labels")) or term_in_text(expected_text, query):
        return "ENTITY_ANCHOR"
    if expected_shape == "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT":
        return "EVIDENCE_REQUIREMENT_SUMMARY"
    if expected_shape == "TABLE_ROW_VALUE":
        return "ROW_SUMMARY_LABEL"
    if expected_shape in {"LOCATION_PLUS_CONTENT", "EVIDENCE_LOCATOR_WITH_CONTENT"}:
        return "RANGE_OR_LOCATION_LABEL"
    return "AMBIGUOUS_NEEDS_HUMAN_REVIEW"


def classify_must_contain_term_role(
    *,
    term: str,
    query: str,
    evidence_summary: Mapping[str, Any],
    fail_closed_reason: str,
) -> str:
    if not term:
        return "AMBIGUOUS_NEEDS_HUMAN_REVIEW"
    if looks_like_policy_placeholder(term) or "POLICY_PENDING" in fail_closed_reason:
        return "POLICY_GUARDRAIL_TERM"
    if looks_like_locator_text(term) or term_in_any(term, evidence_summary.get("locations")):
        return "REQUIRED_LOCATION_OR_RANGE_HINT"
    if term_in_any(term, evidence_summary.get("headers")):
        return "REQUIRED_HEADER_ANCHOR"
    if term_in_any(term, evidence_summary.get("values")) and looks_like_value(term):
        return "REQUIRED_TARGET_VALUE"
    if term_in_any(term, evidence_summary.get("row_labels")):
        return "REQUIRED_ENTITY_ANCHOR"
    if term_in_text(term, query):
        return "KEYWORD_ONLY"
    if term_in_any(term, evidence_summary.get("values")):
        return "REQUIRED_TARGET_VALUE"
    return "AMBIGUOUS_NEEDS_HUMAN_REVIEW"


def metrics_from_outputs(
    *,
    probe_input_rows: list[dict[str, Any]],
    answer_outputs: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    input_errors: list[str],
) -> dict[str, Any]:
    expected_role_counts = Counter(clean(row.get("expected_answer_text_role")) for row in role_rows)
    must_role_counts: Counter[str] = Counter()
    for row in role_rows:
        for item in row.get("must_contain_terms_roles") or []:
            if isinstance(item, Mapping):
                must_role_counts[clean(item.get("role"))] += 1
    answer_count = sum(1 for row in answer_outputs if clean(row.get("answer")))
    abstain_count = sum(1 for row in answer_outputs if clean(row.get("answer_type")) == "ABSTAIN" or clean(row.get("abstain_reason")))
    anchor_summary_roles = {
        "ENTITY_ANCHOR",
        "HEADER_OR_COLUMN_ANCHOR",
        "ROW_SUMMARY_LABEL",
        "RANGE_OR_LOCATION_LABEL",
        "EVIDENCE_REQUIREMENT_SUMMARY",
        "POLICY_OR_REVIEW_PLACEHOLDER",
    }
    must_anchor_roles = {
        "REQUIRED_ENTITY_ANCHOR",
        "REQUIRED_HEADER_ANCHOR",
        "REQUIRED_LOCATION_OR_RANGE_HINT",
        "KEYWORD_ONLY",
        "POLICY_GUARDRAIL_TERM",
    }
    return {
        "xlsx_rows": len(probe_input_rows),
        "answer_allowed_xlsx_rows": sum(1 for row in probe_input_rows if parse_bool(row.get("answer_allowed"))),
        "llm_answer_probe_row_count": len(answer_outputs),
        "llm_answer_count": answer_count,
        "llm_abstain_count": abstain_count,
        "llm_invalid_json_count": sum(1 for row in answer_outputs if not parse_bool(row.get("parse_ok"))),
        "llm_shape_failure_count": sum(
            1
            for row in answer_outputs
            if clean(row.get("llm_smoke_status")) == "DIAGNOSTIC_FAILURE"
        ),
        "llm_unsupported_claim_count": sum(int_or_zero(row.get("llm_unsupported_claim_count")) for row in answer_outputs),
        "llm_gold_leakage_suspected_count": sum(1 for row in answer_outputs if parse_bool(row.get("llm_gold_leakage_suspected"))),
        "llm_citation_missing_count": sum(1 for row in answer_outputs if parse_bool(row.get("llm_citation_missing"))),
        "llm_citation_not_in_context_count": sum(
            1 for row in answer_outputs if parse_bool(row.get("llm_citation_not_in_context"))
        ),
        "llm_locator_only_answer_count": sum(1 for row in answer_outputs if parse_bool(row.get("llm_locator_only_answer"))),
        "llm_keyword_echo_only_count": sum(1 for row in answer_outputs if parse_bool(row.get("llm_keyword_echo_only"))),
        "expected_answer_text_role_counts": dict(expected_role_counts),
        "must_contain_terms_role_counts": dict(must_role_counts),
        "expected_answer_text_final_answer_count": sum(
            1 for row in role_rows if parse_bool(row.get("does_expected_answer_text_look_like_final_answer"))
        ),
        "expected_answer_text_anchor_or_summary_only_count": sum(
            expected_role_counts.get(role, 0) for role in anchor_summary_roles
        ),
        "must_contain_terms_actual_value_row_count": sum(
            1 for row in role_rows if parse_bool(row.get("does_must_contain_include_actual_value"))
        ),
        "must_contain_terms_keyword_header_entity_anchor_only_row_count": sum(
            1
            for row in role_rows
            if row.get("must_contain_terms_roles")
            and all(
                isinstance(item, Mapping) and clean(item.get("role")) in must_anchor_roles
                for item in row.get("must_contain_terms_roles") or []
            )
        ),
        "human_review_required_count": sum(1 for row in role_rows if parse_bool(row.get("human_review_required"))),
        "human_review_required_query_ids": [
            clean(row.get("query_id")) for row in role_rows if parse_bool(row.get("human_review_required"))
        ],
        "answer_prompt_leakage_error_count": len(input_errors),
    }


def build_report(
    *,
    run_id: str,
    generated_at: str,
    source_artifact_dir: Path,
    inputs_path: Path,
    evidence_objects_path: Path,
    compiled_answers_path: Path,
    artifact_dir: Path,
    llm_inputs_path: Path,
    outputs_path: Path,
    role_jsonl_path: Path,
    role_csv_path: Path,
    report_path: Path,
    report_csv_path: Path,
    manifest_path: Path,
    model: str,
    backend: str,
    base_url: str,
    generated_metrics: Mapping[str, Any],
    llm_meta: Mapping[str, Any],
    input_errors: list[str],
) -> dict[str, Any]:
    diagnostic_grounding_failure_count = sum(
        int_or_zero(generated_metrics.get(key))
        for key in (
            "llm_invalid_json_count",
            "llm_unsupported_claim_count",
            "llm_citation_missing_count",
            "llm_citation_not_in_context_count",
            "llm_locator_only_answer_count",
            "llm_keyword_echo_only_count",
        )
    )
    status = "PASS" if not input_errors and not llm_meta.get("blockers") and not diagnostic_grounding_failure_count else "PASS_WITH_WARNINGS"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": status,
        "artifact_dir": repo_relative(artifact_dir),
        "manifest_path": repo_relative(manifest_path),
        "llm_answer_probe_inputs_path": repo_relative(llm_inputs_path),
        "llm_answer_probe_outputs_path": repo_relative(outputs_path),
        "gold_intent_role_probe_jsonl_path": repo_relative(role_jsonl_path),
        "gold_intent_role_probe_csv_path": repo_relative(role_csv_path),
        "report_json_path": repo_relative(report_path),
        "report_csv_path": repo_relative(report_csv_path),
        "source_artifact_dir": repo_relative(source_artifact_dir),
        "source_inputs": {
            "answer_generation_inputs": artifact_entry(inputs_path),
            "evidence_objects": artifact_entry(evidence_objects_path),
            "compiled_answers": artifact_entry(compiled_answers_path),
        },
        "llm_model": model,
        "llm_backend": backend,
        "llm_base_url": base_url,
        "prompt_version": PROMPT_VERSION,
        "local_llm_run": parse_bool(llm_meta.get("local_llm_run")),
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "official_xlsx_answer_eval_denominator": 0,
        "official_answer_denominator": 0,
        "promotion_denominator": 0,
        "gold_intent_probe_used_for_scoring": False,
        "expected_answer_text_used_in_answer_prompt": False,
        "must_contain_terms_used_in_answer_prompt": False,
        "expected_evidence_location_used_in_answer_prompt": False,
        "answer_prompt_leakage_errors": input_errors,
        "llm_blockers": list(llm_meta.get("blockers") or []),
        "grounding_validation_status": "PASS" if diagnostic_grounding_failure_count == 0 else "DIAGNOSTIC_FAILURE",
        "diagnostic_grounding_failure_count": diagnostic_grounding_failure_count,
        "llm_shape_failure_count": generated_metrics.get("llm_shape_failure_count", 0),
        "guardrails": diagnostic_guardrails(),
        **dict(generated_metrics),
    }


def answer_prompt_leakage_errors(
    probe_input_rows: Iterable[Mapping[str, Any]],
    source_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for row in probe_input_rows:
        if not parse_bool(row.get("answer_allowed")):
            if clean(row.get("answer_prompt")) or row.get("answer_prompt_payload"):
                errors.append(f"{clean(row.get('query_id'))}: disallowed row has answer prompt")
            continue
        prompt_text = clean(row.get("answer_prompt"))
        prompt_payload = row.get("answer_prompt_payload") if isinstance(row.get("answer_prompt_payload"), Mapping) else {}
        payload_text = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)
        for key in BANNED_ANSWER_PROMPT_KEYS:
            if key in prompt_text or key in payload_text:
                errors.append(f"{clean(row.get('query_id'))}: banned prompt key {key}")
        source = source_by_id.get(clean(row.get("query_id")), {})
        evidence_text = flatten_text(prompt_payload)
        for field in ("expected_answer_text", "expected_evidence_location", "expected_current_evidence_location"):
            value = clean(source.get(field))
            if value and value in prompt_text and not term_in_text(value, evidence_text):
                errors.append(f"{clean(row.get('query_id'))}: banned prompt value from {field}")
        for term in string_list(source.get("must_contain_terms")):
            if term and term in prompt_text and not term_in_text(term, evidence_text):
                errors.append(f"{clean(row.get('query_id'))}: must term appears without evidence support")
    return errors


def parse_probe_answer_json(value: object, *, fallback_query_id: str) -> tuple[dict[str, Any], bool]:
    text = clean(value)
    if not text:
        return abstain_probe_answer(fallback_query_id, "empty LLM response"), False
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1).strip())
    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            raw_schema_ok = is_raw_probe_answer_schema(parsed, fallback_query_id=fallback_query_id)
            normalized = normalize_probe_answer(parsed, fallback_query_id=fallback_query_id)
            return normalized, raw_schema_ok and is_probe_answer_schema(normalized)
    return abstain_probe_answer(fallback_query_id, "invalid JSON"), False


def is_raw_probe_answer_schema(value: Mapping[str, Any], *, fallback_query_id: str) -> bool:
    required = {
        "query_id",
        "answer",
        "answer_type",
        "citations",
        "used_evidence_fields",
        "unsupported_claims",
        "abstain_reason",
        "confidence",
    }
    if not required.issubset(set(value.keys())):
        return False
    if clean(value.get("query_id")) != fallback_query_id:
        return False
    answer_type = clean(value.get("answer_type")).upper()
    if answer_type not in ANSWER_TYPES:
        return False
    if not isinstance(value.get("citations"), list):
        return False
    if not isinstance(value.get("used_evidence_fields"), list):
        return False
    if not isinstance(value.get("unsupported_claims"), list):
        return False
    if clean(value.get("confidence")).lower() not in {"low", "medium", "high"}:
        return False
    if answer_type == "ABSTAIN":
        return bool(clean(value.get("abstain_reason")) or not clean(value.get("answer")))
    return bool(clean(value.get("answer")))


def normalize_probe_answer(value: Mapping[str, Any], *, fallback_query_id: str) -> dict[str, Any]:
    answer_type = clean(value.get("answer_type") or value.get("answer_shape")).upper()
    if answer_type not in ANSWER_TYPES:
        if clean(value.get("abstain_reason")) and not clean(value.get("answer")):
            answer_type = "ABSTAIN"
        elif "ROW" in answer_type:
            answer_type = "ROW_SUMMARY"
        elif "RANGE" in answer_type or "COLUMN" in answer_type or "TABLE" in answer_type:
            answer_type = "RANGE_SUMMARY"
        elif "LOCATION" in answer_type:
            answer_type = "LOCATION_PLUS_CONTENT"
        else:
            answer_type = "ROW_SUMMARY" if clean(value.get("answer")) else "ABSTAIN"
    citations = value.get("citations") if isinstance(value.get("citations"), list) else []
    used_fields = value.get("used_evidence_fields") if isinstance(value.get("used_evidence_fields"), list) else []
    unsupported = value.get("unsupported_claims") if isinstance(value.get("unsupported_claims"), list) else []
    confidence = clean(value.get("confidence")).lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    return {
        "query_id": clean(value.get("query_id")) or fallback_query_id,
        "answer": clean(value.get("answer")),
        "answer_type": answer_type,
        "citations": [normalize_probe_citation(item) for item in citations if isinstance(item, Mapping)],
        "used_evidence_fields": [clean(item) for item in used_fields if clean(item)],
        "unsupported_claims": [clean(item) for item in unsupported if clean(item)],
        "abstain_reason": clean(value.get("abstain_reason")),
        "confidence": confidence,
    }


def is_probe_answer_schema(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    if clean(value.get("answer_type")) not in ANSWER_TYPES:
        return False
    if not isinstance(value.get("citations"), list):
        return False
    if clean(value.get("answer_type")) == "ABSTAIN":
        return bool(clean(value.get("abstain_reason")) or not clean(value.get("answer")))
    return bool(clean(value.get("answer")))


def abstain_probe_answer(query_id: str, reason: str) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "answer": "",
        "answer_type": "ABSTAIN",
        "citations": [],
        "used_evidence_fields": [],
        "unsupported_claims": [],
        "abstain_reason": reason,
        "confidence": "low",
    }


def normalize_probe_citation(value: Mapping[str, Any]) -> dict[str, str]:
    locator = value.get("locator") if isinstance(value.get("locator"), Mapping) else {}
    return {
        "file": clean(value.get("file") or locator.get("file")),
        "sheet": clean(value.get("sheet") or locator.get("sheet")),
        "range": clean(value.get("range") or value.get("cell") or locator.get("range") or locator.get("cell")),
        "source": clean(value.get("source") or locator.get("source")),
        "search_unit_id": clean(value.get("search_unit_id") or locator.get("search_unit_id")),
        "document_version_id": clean(value.get("document_version_id") or locator.get("document_version_id")),
    }


def valid_probe_citation(value: Mapping[str, Any]) -> bool:
    return bool(clean(value.get("sheet")) and clean(value.get("range")) and clean(value.get("source")))


def validate_probe_citations(citations: list[Any], prompt_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not citations:
        return {
            "status": "citation_missing",
            "unsupported_count": 0,
            "failure_reasons": ["citation_missing"],
        }
    supported_locators = prompt_supported_locators(prompt_payload)
    if not supported_locators:
        return {
            "status": "prompt_locator_missing",
            "unsupported_count": len(citations),
            "failure_reasons": ["prompt_locator_missing"],
        }

    unsupported_count = 0
    reasons: list[str] = []
    for citation in citations:
        if not isinstance(citation, Mapping) or not valid_probe_citation(citation):
            unsupported_count += 1
            reasons.append("citation_missing_required_fields")
            continue
        support_reason = citation_support_failure_reason(citation, supported_locators)
        if support_reason:
            unsupported_count += 1
            reasons.append(support_reason)
    reasons = unique_clean(reasons)
    return {
        "status": "PASS" if unsupported_count == 0 else "citation_not_in_retrieved_context",
        "unsupported_count": unsupported_count,
        "failure_reasons": reasons,
    }


def prompt_supported_locators(prompt_payload: Mapping[str, Any]) -> list[dict[str, str]]:
    locators: list[dict[str, str]] = []

    def add(value: object) -> None:
        locator = safe_citation_locator(value)
        if clean(locator.get("sheet")) and (clean(locator.get("range")) or clean(locator.get("cell"))):
            locators.append(locator)

    add(prompt_payload.get("citation_locator"))
    add(prompt_payload.get("sheet_range_cell_locator"))
    evidence = prompt_payload.get("evidence") if isinstance(prompt_payload.get("evidence"), Mapping) else {}
    add(evidence.get("locator"))
    add(evidence.get("selected_searchunit_locator"))
    add(evidence.get("content_source_locator"))
    add(
        {
            "file": evidence.get("file_name"),
            "sheet": evidence.get("sheet"),
            "range": evidence.get("range"),
            "cell": evidence.get("cell"),
            "search_unit_id": evidence.get("selected_search_unit_id"),
        }
    )
    return unique_locators(locators)


def citation_support_failure_reason(citation: Mapping[str, Any], locators: list[Mapping[str, str]]) -> str:
    citation_sheet = normalize_locator_sheet(citation.get("sheet"))
    citation_range = clean(citation.get("range"))
    same_sheet_locators = [
        locator for locator in locators if normalize_locator_sheet(locator.get("sheet")) == citation_sheet
    ]
    if not same_sheet_locators:
        return "wrong_sheet_citation"
    identity_reason = citation_identity_failure_reason(citation, same_sheet_locators)
    if identity_reason:
        return identity_reason
    for locator in same_sheet_locators:
        if ranges_exact_match(citation_range, locator.get("range")) or ranges_exact_match(citation_range, locator.get("cell")):
            return ""
    for locator in same_sheet_locators:
        if ranges_overlap(citation_range, locator.get("range")) or ranges_overlap(citation_range, locator.get("cell")):
            return "partial_range_overlap"
    return "wrong_range_citation"


def citation_identity_failure_reason(citation: Mapping[str, Any], locators: list[Mapping[str, str]]) -> str:
    supplied_fields = [
        ("file", "wrong_file_citation"),
        ("document_version_id", "wrong_document_version_citation"),
        ("search_unit_id", "wrong_search_unit_citation"),
    ]
    for field, reason in supplied_fields:
        if any(clean(locator.get(field)) for locator in locators) and not clean(citation.get(field)):
            return f"missing_{field}_citation"
        value = clean(citation.get(field))
        if not value:
            continue
        if not any(locator_identity_matches(field, value, locator.get(field)) for locator in locators):
            return reason
    return ""


def locator_identity_matches(field: str, left: object, right: object) -> bool:
    left_text = clean(left)
    right_text = clean(right)
    if not left_text or not right_text:
        return False
    if field == "file":
        return Path(left_text).name.casefold() == Path(right_text).name.casefold()
    return left_text == right_text


def ranges_exact_match(left: object, right: object) -> bool:
    left_text = normalize_range_text(left)
    right_text = normalize_range_text(right)
    return bool(left_text and right_text and left_text == right_text)


def ranges_overlap(left: str, right: str) -> bool:
    left_bounds = a1_bounds(left)
    right_bounds = a1_bounds(right)
    if left_bounds and right_bounds:
        l_min_col, l_min_row, l_max_col, l_max_row = left_bounds
        r_min_col, r_min_row, r_max_col, r_max_row = right_bounds
        return not (
            l_max_col < r_min_col
            or r_max_col < l_min_col
            or l_max_row < r_min_row
            or r_max_row < l_min_row
        )
    return normalize_range_text(left) == normalize_range_text(right)


def a1_bounds(value: str) -> tuple[int, int, int, int] | None:
    text = clean(value).replace("$", "")
    if "!" in text:
        text = text.rsplit("!", 1)[1]
    match = re.fullmatch(r"([A-Za-z]{1,4})(\d+)(?::([A-Za-z]{1,4})(\d+))?", text)
    if not match:
        return None
    start_col = column_number(match.group(1))
    start_row = int(match.group(2))
    end_col = column_number(match.group(3) or match.group(1))
    end_row = int(match.group(4) or match.group(2))
    min_col, max_col = sorted([start_col, end_col])
    min_row, max_row = sorted([start_row, end_row])
    return min_col, min_row, max_col, max_row


def column_number(value: str) -> int:
    number = 0
    for char in clean(value).upper():
        number = number * 26 + (ord(char) - ord("A") + 1)
    return number


def normalize_locator_sheet(value: object) -> str:
    return clean(value).casefold()


def normalize_range_text(value: object) -> str:
    return clean(value).replace("$", "").upper()


def unique_locators(locators: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for locator in locators:
        key = (
            clean(locator.get("file")),
            normalize_locator_sheet(locator.get("sheet")),
            normalize_range_text(locator.get("range") or locator.get("cell")),
        )
        if key not in seen:
            seen.add(key)
            out.append(dict(locator))
    return out


def xlsx_locator(evidence: Mapping[str, Any]) -> dict[str, str]:
    locator = evidence.get("locator") if isinstance(evidence.get("locator"), Mapping) else {}
    return compact_mapping(
        {
            "file": clean(evidence.get("file_name") or locator.get("file")),
            "sheet": clean(evidence.get("sheet") or locator.get("sheet")),
            "range": clean(evidence.get("range") or evidence.get("cell") or locator.get("range") or locator.get("cell")),
            "cell": clean(evidence.get("cell") or locator.get("cell")),
            "search_unit_id": clean(evidence.get("selected_search_unit_id") or locator.get("search_unit_id")),
            "document_version_id": clean(evidence.get("document_version_id") or locator.get("document_version_id")),
        }
    )


def safe_query_binding(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return compact_mapping(
        {
            "query": clean(value.get("query")),
            "matched_entity_values": string_list(value.get("matched_entity_values"))[:12],
            "matched_header_labels": string_list(value.get("matched_header_labels"))[:12],
            "query_bound_values": mapping_list(value.get("query_bound_values"))[:12],
            "target_column_bound": parse_bool(value.get("target_column_bound")),
            "workbook_vocabulary_source": clean(value.get("workbook_vocabulary_source")),
        }
    )


def evidence_summary_for_role_probe(probe_input: Mapping[str, Any]) -> dict[str, Any]:
    payload = probe_input.get("answer_prompt_payload") if isinstance(probe_input.get("answer_prompt_payload"), Mapping) else {}
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), Mapping) else {}
    loc = payload.get("sheet_range_cell_locator") if isinstance(payload.get("sheet_range_cell_locator"), Mapping) else {}
    row_values = mapping_list(evidence.get("row_values"))
    column_values = mapping_list(evidence.get("column_values"))
    cell_values = mapping_list(evidence.get("cell_values"))
    values = [
        clean(evidence.get("value")),
        *[clean(item.get("value")) for item in row_values + column_values + cell_values],
    ]
    row_labels = [
        clean(evidence.get("row_label")),
        *[clean(item.get("row_label")) for item in row_values + cell_values],
    ]
    headers = [
        clean(evidence.get("column_label")),
        *string_list(evidence.get("header_context")),
        *[clean(item.get("column_label")) for item in row_values + column_values + cell_values],
    ]
    locations = [
        clean(evidence.get("sheet")),
        clean(evidence.get("range")),
        clean(evidence.get("cell")),
        clean(loc.get("sheet")),
        clean(loc.get("range")),
        clean(loc.get("cell")),
    ]
    return {
        "values": unique_clean(values),
        "row_labels": unique_clean(row_labels),
        "headers": unique_clean(headers),
        "locations": unique_clean(locations),
        "text": flatten_text(payload),
    }


def text_supported_by(answer: str, evidence_text: str) -> bool:
    if not clean(answer):
        return True
    answer_norm = normalize_for_match(answer)
    evidence_norm = normalize_for_match(evidence_text)
    if answer_norm and answer_norm in evidence_norm:
        return True
    tokens = meaningful_tokens(answer)
    if not tokens:
        return True
    missing = [token for token in tokens if normalize_for_match(token) not in evidence_norm]
    return len(missing) <= max(1, len(tokens) // 5)


def gold_terms_only_in_answer(*, answer: str, evidence_text: str, source_row: Mapping[str, Any]) -> list[str]:
    leaked: list[str] = []
    for term in [clean(source_row.get("expected_answer_text")), *string_list(source_row.get("must_contain_terms"))]:
        if not term:
            continue
        if term_in_text(term, answer) and not term_in_text(term, evidence_text):
            leaked.append(term)
    return unique_clean(leaked)


def looks_like_locator_only_answer(answer: str, probe_input: Mapping[str, Any]) -> bool:
    text = clean(answer)
    if not text:
        return False
    if looks_like_locator_text(text):
        return True
    payload = probe_input.get("answer_prompt_payload") if isinstance(probe_input.get("answer_prompt_payload"), Mapping) else {}
    loc = payload.get("sheet_range_cell_locator") if isinstance(payload.get("sheet_range_cell_locator"), Mapping) else {}
    loc_terms = [clean(loc.get("sheet")), clean(loc.get("range")), clean(loc.get("cell"))]
    loc_only = " ".join(term for term in loc_terms if term)
    return bool(loc_only and normalize_for_match(text) == normalize_for_match(loc_only))


def looks_like_keyword_echo_only(answer: str, query: str, source_row: Mapping[str, Any]) -> bool:
    answer_tokens = set(meaningful_tokens(answer))
    if not answer_tokens:
        return False
    query_tokens = set(meaningful_tokens(query))
    if answer_tokens and answer_tokens.issubset(query_tokens):
        return True
    gold_terms = [clean(source_row.get("expected_answer_text")), *string_list(source_row.get("must_contain_terms"))]
    return any(normalize_for_match(answer) == normalize_for_match(term) for term in gold_terms if clean(term))


def final_answer_like(
    expected_text: str,
    llm_answer: str,
    deterministic_answer: str,
    evidence_summary: Mapping[str, Any],
) -> bool:
    if not expected_text:
        return False
    if looks_like_value(expected_text) and term_in_any(expected_text, evidence_summary.get("values")):
        return True
    if term_in_text(expected_text, llm_answer) or term_in_text(expected_text, deterministic_answer):
        if looks_like_value(expected_text) or term_in_any(expected_text, evidence_summary.get("values")):
            return True
    return False


def role_rationale(
    expected_role: str,
    term_roles: list[Mapping[str, str]],
    expected_final: bool,
    must_has_value: bool,
    must_keyword_only: bool,
) -> str:
    parts = [f"expected={expected_role}"]
    if expected_final:
        parts.append("expected text resembles a final value")
    if must_has_value:
        parts.append("must terms include evidence values")
    if must_keyword_only:
        parts.append("must terms look like keyword/header/entity anchors")
    if any(clean(item.get("role")) == "AMBIGUOUS_NEEDS_HUMAN_REVIEW" for item in term_roles):
        parts.append("ambiguous term requires review")
    return "; ".join(parts)


def looks_like_value(value: str) -> bool:
    text = clean(value)
    return bool(re.search(r"\d", text) or re.search(r"[:=]|%|원|명|건|개|호선|년|월", text))


def looks_like_policy_placeholder(value: str) -> bool:
    text = normalize_for_match(value)
    return any(token in text for token in ("pending", "review", "placeholder", "tbd", "needsreview", "policy"))


def looks_like_locator_text(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    return bool(
        re.fullmatch(r"[A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?", text)
        or re.search(r"\bsheet\b|\brange\b|\bcell\b|!|\.xlsx\b", text, flags=re.IGNORECASE)
    )


def term_in_any(term: str, values: object) -> bool:
    return any(term_in_text(term, clean(value)) for value in listish(values))


def term_in_text(term: str, text: str) -> bool:
    term_norm = normalize_for_match(term)
    text_norm = normalize_for_match(text)
    return bool(term_norm and term_norm in text_norm)


def meaningful_tokens(value: str) -> list[str]:
    text = clean(value)
    raw = re.findall(r"[0-9A-Za-z가-힣_,.%]+", text)
    tokens = []
    for token in raw:
        token = token.strip("_,.%")
        if len(token) <= 1 and not token.isdigit():
            continue
        if normalize_for_match(token) in {"row", "column", "value", "sheet", "range", "cell", "evidence", "scope"}:
            continue
        tokens.append(token)
    return tokens


def normalize_for_match(value: object) -> str:
    return re.sub(r"\s+", "", clean(value).lower())


def flatten_text(value: object) -> str:
    parts: list[str] = []

    def walk(item: object) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                parts.append(clean(key))
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        else:
            text = clean(item)
            if text:
                parts.append(text)

    walk(value)
    return " ".join(parts)


def find_latest_source_artifact(root: Path) -> Path:
    candidates = [
        path
        for path in root.glob("pdf_xlsx_answer_shape_xlsx_generalization_audit_*")
        if (path / "answer_generation_inputs.jsonl").exists()
        and (path / "evidence_objects.jsonl").exists()
        and (path / "compiled_answers.jsonl").exists()
    ]
    if not candidates:
        candidates = [
            path
            for path in root.glob("pdf_xlsx_answer_shape_xlsx_query_bound_context_*")
            if (path / "answer_generation_inputs.jsonl").exists()
            and (path / "evidence_objects.jsonl").exists()
            and (path / "compiled_answers.jsonl").exists()
        ]
    if not candidates:
        raise SystemExit("No source artifact with answer_generation_inputs/evidence_objects/compiled_answers found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def role_csv_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": clean(row.get("query_id")),
            "expected_answer_text_role": clean(row.get("expected_answer_text_role")),
            "must_contain_terms_roles_json": json.dumps(row.get("must_contain_terms_roles") or [], ensure_ascii=False),
            "does_expected_answer_text_look_like_final_answer": parse_bool(
                row.get("does_expected_answer_text_look_like_final_answer")
            ),
            "does_must_contain_include_actual_value": parse_bool(row.get("does_must_contain_include_actual_value")),
            "does_must_contain_look_keyword_only": parse_bool(row.get("does_must_contain_look_keyword_only")),
            "human_review_required": parse_bool(row.get("human_review_required")),
            "rationale": clean(row.get("rationale")),
        }
        for row in rows
    ]


def report_csv_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": clean(row.get("query_id")),
            "trace_id": clean(row.get("trace_id")),
            "track": clean(row.get("track")),
            "eval_mode": clean(row.get("eval_mode")),
            "answer_allowed": parse_bool(row.get("answer_allowed")),
            "fail_closed_reason": clean(row.get("fail_closed_reason")),
            "llm_smoke_status": clean(row.get("llm_smoke_status")),
            "raw_output_status": clean(row.get("raw_output_status")),
            "parser_status": clean(row.get("parser_status")),
            "content_shape_status": clean(row.get("content_shape_status")),
            "citation_validation_status": clean(row.get("citation_validation_status")),
            "official_metric_included": parse_bool(row.get("official_metric_included")),
            "answer_generation_denominator_included": parse_bool(row.get("answer_generation_denominator_included")),
            "failure_reason": clean(row.get("failure_reason")),
            "prompt_hash": clean(row.get("prompt_hash")),
            "context_hash": clean(row.get("context_hash")),
            "answer_type": clean(row.get("answer_type")),
            "answer": clean(row.get("answer")),
            "abstain_reason": clean(row.get("abstain_reason")),
            "parse_ok": parse_bool(row.get("parse_ok")),
            "unsupported_claim_count": int_or_zero(row.get("llm_unsupported_claim_count")),
            "gold_leakage_suspected": parse_bool(row.get("llm_gold_leakage_suspected")),
            "citation_missing": parse_bool(row.get("llm_citation_missing")),
            "citation_not_in_context": parse_bool(row.get("llm_citation_not_in_context")),
            "citation_support_status": clean(row.get("llm_citation_support_status")),
            "citation_failure_reasons": json.dumps(row.get("llm_citation_failure_reasons") or [], ensure_ascii=False),
            "locator_only_answer": parse_bool(row.get("llm_locator_only_answer")),
            "keyword_echo_only": parse_bool(row.get("llm_keyword_echo_only")),
        }
        for row in rows
    ]


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def diagnostic_guardrails() -> dict[str, bool]:
    return {
        "retrieval_ranking_modified": False,
        "parser_modified": False,
        "diagnostic_llm_output_schema_hardened": True,
        "chunking_modified": False,
        "embeddings_modified": False,
        "db_mutation_run": False,
        "searchunit_mutation_run": False,
        "gold_file_mutation_run": False,
        "broad_sheet_workbook_fallback_promoted": False,
        "source_workbook_probe_promoted": False,
    }


def keyed_by_query_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {clean(row.get("query_id")): row for row in rows if clean(row.get("query_id"))}


def compact_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        compact[str(key)] = item
    return compact


def stable_sha256(value: object) -> str:
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def listish(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if isinstance(value, str):
        if ";" in value:
            return [clean(item) for item in value.split(";") if clean(item)]
        if "|" in value:
            return [clean(item) for item in value.split("|") if clean(item)]
        return [clean(value)] if clean(value) else []
    return []


def unique_clean(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = clean(value)
        key = normalize_for_match(text)
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def nested(value: Any, *keys: Any) -> Any:
    current = value
    for key in keys:
        if isinstance(current, Mapping):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return None
    return current


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


def int_or_zero(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def json_escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
