"""Run a local LLM model for PDF/XLSX answer-shape diagnostics.

This is diagnostic-only. It calls only a local Docker llama.cpp endpoint or an
explicitly selected local Ollama endpoint, records ``external_live_llm_run=false``
and ``promotion_evidence=false``, and refuses to fall back to cloud or optional
judges.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from eval.harness.pdf_xlsx_answer_evidence_serializer import serialize_input_rows
from eval.harness.pdf_xlsx_deterministic_answer_compiler import compile_evidence_rows

DEFAULT_BACKEND = "llamacpp"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LLAMACPP_BASE_URL = "http://localhost:8081/v1"
DEFAULT_CONTRACT = REPO_ROOT / "docs" / "eval" / "pdf_xlsx_answer_intent_prompt_contract.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = run_answers(
        inputs_path=Path(args.inputs),
        model=args.model,
        output_path=Path(args.output) if args.output else None,
        contract_path=Path(args.contract),
        backend=args.backend,
        base_url=args.base_url or (args.ollama_base_url if args.backend == "ollama" else ""),
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
        max_rows=args.max_rows,
        evidence_output_path=Path(args.evidence_output) if args.evidence_output else None,
        compiled_output_path=Path(args.compiled_output) if args.compiled_output else None,
        compiled_answers_path=Path(args.compiled_answers) if args.compiled_answers else None,
        deterministic_only=args.deterministic_only,
        run_id=args.run_id,
    )
    print_json(status)
    return 0 if status["status"] in {"PASS", "PASS_DETERMINISTIC_ONLY"} else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, help="Path to answer_generation_inputs.jsonl")
    parser.add_argument("--model", required=True, help="Local model name")
    parser.add_argument("--output", default="", help="Defaults to local_llm_answers.jsonl next to inputs")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument(
        "--backend",
        choices=["llamacpp", "ollama"],
        default=os.environ.get("PDF_XLSX_LOCAL_LLM_BACKEND", DEFAULT_BACKEND),
        help="Local backend type. Defaults to the repo Docker llama.cpp service.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PDF_XLSX_LOCAL_LLM_BASE_URL", ""),
        help="Local backend base URL. Defaults to http://localhost:8081/v1 for llama.cpp.",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--max-rows", type=int, default=0, help="0 means all rows")
    parser.add_argument("--run-id", default="", help="Optional repair run id for deterministic artifacts")
    parser.add_argument("--evidence-output", default="", help="Defaults to evidence_objects.jsonl next to output")
    parser.add_argument("--compiled-output", default="", help="Defaults to compiled_answers.jsonl next to output")
    parser.add_argument("--compiled-answers", default="", help="Use precompiled answers instead of compiling inputs")
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Write compiled answers as diagnostic output without calling the local LLM.",
    )
    return parser.parse_args(argv)


def run_answers(
    *,
    inputs_path: Path,
    model: str,
    output_path: Path | None,
    contract_path: Path,
    backend: str,
    base_url: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
    max_rows: int = 0,
    evidence_output_path: Path | None = None,
    compiled_output_path: Path | None = None,
    compiled_answers_path: Path | None = None,
    deterministic_only: bool = False,
    run_id: str = "",
) -> dict[str, Any]:
    base_url = resolve_base_url(backend, base_url)
    output_path = output_path or inputs_path.parent / "local_llm_answers.jsonl"
    evidence_output_path = evidence_output_path or output_path.parent / "evidence_objects.jsonl"
    compiled_output_path = compiled_output_path or output_path.parent / "compiled_answers.jsonl"
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = read_jsonl(inputs_path)
    if max_rows > 0:
        rows = rows[:max_rows]

    if compiled_answers_path and compiled_answers_path.exists():
        compiled_rows = read_jsonl(compiled_answers_path)
        evidence_rows: list[dict[str, Any]] = []
    else:
        evidence_rows = serialize_input_rows(rows, run_id=run_id)
        compiled_rows = compile_evidence_rows(evidence_rows, run_id=run_id)
        write_jsonl(evidence_output_path, evidence_rows)
        write_jsonl(compiled_output_path, compiled_rows)

    if deterministic_only:
        output_rows = [
            output_row_from_compiled(
                compiled_row,
                run_id=run_id,
                llm_polish_run=False,
                llm_polish_skipped_reason="deterministic_only",
            )
            for compiled_row in compiled_rows
        ]
        write_jsonl(output_path, output_rows)
        return {
            "status": "PASS_DETERMINISTIC_ONLY",
            "run_id": run_id,
            "inputs": repo_relative(inputs_path),
            "output": repo_relative(output_path),
            "evidence_objects": repo_relative(evidence_output_path),
            "compiled_answers": repo_relative(compiled_output_path),
            "backend": backend,
            "model": model,
            "base_url": base_url,
            "ollama_base_url": base_url if backend == "ollama" else DEFAULT_OLLAMA_BASE_URL,
            "local_llm_run": False,
            "llm_polish_run": False,
            "external_live_llm_run": False,
            "optional_judge_run": False,
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "answers_written": True,
            "row_count": len(output_rows),
            "parse_ok_count": sum(1 for row in output_rows if row["parse_ok"]),
            "repair_parse_ok_count": sum(1 for row in output_rows if row["repair_parse_ok"]),
            "invalid_json_answer_count": sum(1 for row in output_rows if not row["parse_ok"]),
        }

    blockers = entry_blockers(
        inputs_path=inputs_path,
        rows=rows,
        model=model,
        backend=backend,
        base_url=base_url,
    )
    if blockers:
        return {
            "status": "BLOCKED_LOCAL_LLM_UNAVAILABLE",
            "run_id": run_id,
            "inputs": repo_relative(inputs_path),
            "output": repo_relative(output_path),
            "evidence_objects": repo_relative(evidence_output_path),
            "compiled_answers": repo_relative(compiled_output_path),
            "backend": backend,
            "model": model,
            "base_url": base_url,
            "ollama_base_url": base_url if backend == "ollama" else DEFAULT_OLLAMA_BASE_URL,
            "local_llm_run": False,
            "external_live_llm_run": False,
            "optional_judge_run": False,
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "answers_written": False,
            "blockers": blockers,
        }

    contract_excerpt = contract_path.read_text(encoding="utf-8") if contract_path.exists() else ""
    output_rows: list[dict[str, Any]] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, compiled_row in enumerate(compiled_rows, start=1):
            compiled_answer = compiled_row.get("compiled_answer") if isinstance(compiled_row.get("compiled_answer"), Mapping) else {}
            if not parse_bool(compiled_row.get("answer_generation_allowed")) or clean(compiled_answer.get("abstain_reason")):
                output_row = output_row_from_compiled(
                    compiled_row,
                    run_id=run_id,
                    llm_polish_run=False,
                    llm_polish_skipped_reason="compiled_abstain_or_generation_not_allowed",
                )
                output_rows.append(output_row)
                handle.write(json.dumps(output_row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                print(
                    f"[local-llm] {index}/{len(compiled_rows)} {output_row['query_id']} deterministic parse_ok=True",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            prompt = build_polish_prompt(compiled_row, contract_excerpt)
            llm_error = ""
            try:
                answer_json_raw = call_local_llm(
                    backend=backend,
                    base_url=base_url,
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                )
                parsed_answer, raw_parse_ok, parse_ok, repair_parse_ok = parse_or_repair_answer_json(answer_json_raw)
            except Exception as exc:  # keep later rows diagnosable
                llm_error = f"{type(exc).__name__}: {exc}"
                answer_json_raw = json.dumps({"local_llm_error": llm_error}, ensure_ascii=False)
                parsed_answer, raw_parse_ok, parse_ok, repair_parse_ok = {"local_llm_error": llm_error}, False, False, False
            unsupported_claim_added = bool(parse_ok and llm_added_unsupported_claim(parsed_answer, compiled_row))
            if unsupported_claim_added:
                parsed_answer = dict(parsed_answer)
                parsed_answer["failure_mode_if_any"] = "LLM_HALLUCINATED_UNSUPPORTED_CLAIM"
            output_row = {
                "run_id": clean(compiled_row.get("source_input_run_id")) or clean(compiled_row.get("run_id")) or run_id,
                "repair_run_id": run_id,
                "track": clean(compiled_row.get("track")),
                "query_id": clean(compiled_row.get("query_id")),
                "query": clean(compiled_row.get("query")),
                "expected_answer_shape": clean(compiled_row.get("expected_answer_shape")),
                "answer_json_raw": answer_json_raw,
                "parsed_answer": parsed_answer,
                "parse_ok": parse_ok,
                "raw_parse_ok": raw_parse_ok,
                "repair_parse_ok": repair_parse_ok,
                "local_llm_error": llm_error,
                "local_llm_run": True,
                "llm_polish_run": True,
                "llm_polish_skipped_reason": "",
                "deterministic_compiler_run": True,
                "deterministic_compiled_answer_used": False,
                "unsupported_claim_added": unsupported_claim_added,
                "failure_reason": "LLM_HALLUCINATED_UNSUPPORTED_CLAIM" if unsupported_claim_added else "",
                "compiled_answer_draft": compiled_answer,
                "compiled_answer": compiled_answer,
                "evidence_object": compiled_row.get("evidence_object") if isinstance(compiled_row.get("evidence_object"), Mapping) else {},
                "answer_allowed": parse_bool(compiled_row.get("answer_allowed")) or parse_bool(compiled_row.get("answer_generation_allowed")),
                "answer_generation_allowed": parse_bool(compiled_row.get("answer_allowed")) or parse_bool(compiled_row.get("answer_generation_allowed")),
                "answer_generation_blocker": clean(compiled_row.get("answer_generation_blocker")),
                "answer_disallowed_reason": clean(compiled_row.get("answer_disallowed_reason")),
                "fail_closed_reason": clean(compiled_row.get("fail_closed_reason")),
                "content_source_fields": compiled_row.get("content_source_fields")
                if isinstance(compiled_row.get("content_source_fields"), list)
                else [],
                "evidence_quality": compiled_row.get("evidence_quality")
                if isinstance(compiled_row.get("evidence_quality"), Mapping)
                else {},
                "compiler_status": clean(compiled_row.get("compiler_status")),
                "external_live_llm_run": False,
                "optional_judge_run": False,
                "promotion_evidence": False,
                "evidence_role": "diagnostic",
            }
            output_rows.append(output_row)
            handle.write(json.dumps(output_row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            print(
                f"[local-llm] {index}/{len(rows)} {output_row['query_id']} parse_ok={parse_ok}",
                file=sys.stderr,
                flush=True,
            )
    return {
        "status": "PASS",
        "run_id": run_id,
        "inputs": repo_relative(inputs_path),
        "output": repo_relative(output_path),
        "evidence_objects": repo_relative(evidence_output_path),
        "compiled_answers": repo_relative(compiled_output_path),
        "backend": backend,
        "model": model,
        "base_url": base_url,
        "ollama_base_url": base_url if backend == "ollama" else DEFAULT_OLLAMA_BASE_URL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "row_count": len(output_rows),
        "parse_ok_count": sum(1 for row in output_rows if row["parse_ok"]),
        "repair_parse_ok_count": sum(1 for row in output_rows if row["repair_parse_ok"]),
        "invalid_json_answer_count": sum(1 for row in output_rows if not row["parse_ok"]),
        "local_llm_run": any(parse_bool(row.get("local_llm_run")) for row in output_rows),
        "llm_polish_run": any(parse_bool(row.get("llm_polish_run")) for row in output_rows),
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "answers_written": True,
    }


def entry_blockers(
    *,
    inputs_path: Path,
    rows: list[dict[str, Any]],
    model: str,
    backend: str,
    base_url: str,
) -> list[str]:
    blockers: list[str] = []
    if not inputs_path.exists():
        blockers.append(f"inputs missing: {repo_relative(inputs_path)}")
    if not rows:
        blockers.append("inputs JSONL has no rows")
    if not clean(model):
        blockers.append("model is required")
    base_url = resolve_base_url(backend, base_url)
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        blockers.append("local LLM base URL must be http(s)")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        blockers.append("external/cloud LLM endpoints are forbidden; use localhost only")
    if blockers:
        return blockers
    try:
        if backend == "ollama":
            request_json(f"{base_url.rstrip('/')}/api/tags", payload=None, timeout_seconds=5)
        else:
            request_json(f"{base_url.rstrip('/')}/models", payload=None, timeout_seconds=5)
    except Exception as exc:
        blockers.append(f"local {backend} unavailable: {type(exc).__name__}: {exc}")
    return blockers


def build_prompt(input_row: Mapping[str, Any], contract_excerpt: str) -> str:
    contract_short = contract_excerpt[:3000]
    prompt_context = clean(input_row.get("prompt_context"))
    if len(prompt_context) > 4500:
        prompt_context = prompt_context[:4500] + "\n...TRUNCATED_FOR_LOCAL_LLM_CONTEXT_WINDOW..."
    if not prompt_context:
        prompt_context = json.dumps(
            {
                "track": input_row.get("track"),
                "query_id": input_row.get("query_id"),
                "query": input_row.get("query"),
                "expected_answer_shape": input_row.get("expected_answer_shape"),
                "answer_instruction": input_row.get("answer_instruction"),
                "content_target_needed": input_row.get("content_target_needed"),
                "expected_evidence_location": input_row.get("expected_evidence_location"),
                "citation_target_policy": input_row.get("citation_target_policy"),
                "policy": input_row.get("policy"),
                "context": input_row.get("context"),
            },
            ensure_ascii=False,
            indent=2,
        )[:4500]
    return f"""You are evaluating a diagnostic PDF/XLSX RAG answer shape.

Follow these contract rules:
{contract_short}

Return exactly one JSON object and no markdown. Use this schema:
{{
  "answer": "content claim/value/summary first, or empty when abstaining",
  "answer_shape": "one of the expected answer-shape enum values",
  "citations": [
    {{"locator": "page/bbox/sheet/range/cell evidence", "supports_claim": true, "claim": "claim supported by this citation"}}
  ],
  "abstain_reason": "filled when evidence is insufficient, hidden-policy, not-answerable, or policy-pending",
  "used_content_terms": ["terms from the provided context used in the answer"],
  "failure_mode_if_any": "KEYWORD_ECHO_ONLY, LOCATION_ONLY_ANSWER, INSUFFICIENT_CONTEXT, POLICY_PENDING, or empty"
}}

Hard rules:
- Do not answer with only a keyword, sheet/range/cell, page/bbox, file name, or section name.
- XLSX answers must include row label, column/header meaning, visible value, nearby table context, or an explicit abstain_reason.
- PDF answers must include the sentence, paragraph, table value, or section summary, or an explicit abstain_reason.
- Citations must support the answer claim/content, not only the keyword location.
- If evidence is insufficient, do not guess. Fill abstain_reason.
- If the row policy says ABSTAIN_OR_POLICY_PENDING, abstain.
- Keep external_live_llm_run false; this is local diagnostic evidence only.

Diagnostic input row:
{prompt_context}
"""


def build_polish_prompt(compiled_row: Mapping[str, Any], contract_excerpt: str) -> str:
    contract_short = contract_excerpt[:2200]
    compiled_answer = compiled_row.get("compiled_answer") if isinstance(compiled_row.get("compiled_answer"), Mapping) else {}
    evidence_object = compiled_row.get("evidence_object") if isinstance(compiled_row.get("evidence_object"), Mapping) else {}
    payload = {
        "task": "polish_deterministic_pdf_xlsx_diagnostic_answer",
        "query_id": compiled_row.get("query_id"),
        "query": compiled_row.get("query"),
        "expected_answer_shape": compiled_row.get("expected_answer_shape"),
        "compiled_answer_draft": compiled_answer,
        "evidence_object": evidence_object,
        "allowed_claim_text": allowed_claim_text(compiled_row),
    }
    return f"""You are polishing a deterministic diagnostic RAG answer.

Relevant contract excerpt:
{contract_short}

Return exactly one JSON object and no markdown. Use this schema:
{{
  "answer": "natural Korean wording of compiled_answer.answer, or empty when abstaining",
  "answer_shape": "same shape as compiled_answer.answer_shape",
  "citations": [
    {{"locator": "same locator evidence", "supports_claim": true, "claim": "claim supported by the compiled answer"}}
  ],
  "abstain_reason": "same abstain meaning when compiled answer abstains",
  "used_content_terms": ["terms copied from evidence_object or compiled_answer"],
  "failure_mode_if_any": "empty unless preserving a compiled failure mode"
}}

Hard rules:
- Polish only compiled_answer_draft; do not add facts, numbers, labels, units, rows, columns, pages, or claims absent from allowed_claim_text.
- Keep citations attached to the content claim, not to a keyword or locator alone.
- If the compiled answer abstains, keep the abstain.
- If you cannot preserve the schema, return the compiled answer JSON unchanged.

Diagnostic compiled row:
{json.dumps(payload, ensure_ascii=False, indent=2)[:6500]}
"""


def output_row_from_compiled(
    compiled_row: Mapping[str, Any],
    *,
    run_id: str,
    llm_polish_run: bool,
    llm_polish_skipped_reason: str,
) -> dict[str, Any]:
    compiled_answer = (
        dict(compiled_row.get("compiled_answer"))
        if isinstance(compiled_row.get("compiled_answer"), Mapping)
        else {}
    )
    return {
        "run_id": clean(compiled_row.get("source_input_run_id")) or clean(compiled_row.get("run_id")) or run_id,
        "repair_run_id": run_id,
        "track": clean(compiled_row.get("track")),
        "query_id": clean(compiled_row.get("query_id")),
        "query": clean(compiled_row.get("query")),
        "expected_answer_shape": clean(compiled_row.get("expected_answer_shape")),
        "answer_json_raw": json.dumps(compiled_answer, ensure_ascii=False, sort_keys=True),
        "parsed_answer": compiled_answer,
        "parse_ok": is_answer_schema(compiled_answer),
        "raw_parse_ok": is_answer_schema(compiled_answer),
        "repair_parse_ok": False,
        "local_llm_error": "",
        "local_llm_run": False,
        "llm_polish_run": llm_polish_run,
        "llm_polish_skipped_reason": llm_polish_skipped_reason,
        "deterministic_compiler_run": True,
        "deterministic_compiled_answer_used": True,
        "unsupported_claim_added": False,
        "failure_reason": "",
        "compiled_answer_draft": compiled_answer,
        "compiled_answer": compiled_answer,
        "evidence_object": compiled_row.get("evidence_object") if isinstance(compiled_row.get("evidence_object"), Mapping) else {},
        "answer_allowed": parse_bool(compiled_row.get("answer_allowed")) or parse_bool(compiled_row.get("answer_generation_allowed")),
        "answer_generation_allowed": parse_bool(compiled_row.get("answer_allowed")) or parse_bool(compiled_row.get("answer_generation_allowed")),
        "answer_generation_blocker": clean(compiled_row.get("answer_generation_blocker")),
        "answer_disallowed_reason": clean(compiled_row.get("answer_disallowed_reason")),
        "fail_closed_reason": clean(compiled_row.get("fail_closed_reason")),
        "content_source_fields": compiled_row.get("content_source_fields")
        if isinstance(compiled_row.get("content_source_fields"), list)
        else [],
        "evidence_quality": compiled_row.get("evidence_quality") if isinstance(compiled_row.get("evidence_quality"), Mapping) else {},
        "compiler_status": clean(compiled_row.get("compiler_status")),
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }


def call_local_llm(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
) -> str:
    if backend == "ollama":
        return call_ollama(
            base_url=base_url,
            model=model,
            prompt=prompt,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    return call_openai_compatible(
        base_url=base_url,
        model=model,
        prompt=prompt,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
    )


def resolve_base_url(backend: str, base_url: str) -> str:
    if clean(base_url):
        return clean(base_url)
    if backend == "ollama":
        return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return DEFAULT_LLAMACPP_BASE_URL


def call_ollama(
    *,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }
    response = request_json(
        f"{base_url.rstrip('/')}/api/generate",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(response, Mapping):
        return json.dumps(response, ensure_ascii=False)
    return clean(response.get("response")) or json.dumps(response, ensure_ascii=False)


def call_openai_compatible(
    *,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    max_tokens: int,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return a final JSON object only. Do not include reasoning, markdown, or prose.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": int(max_tokens),
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    response = request_json(
        f"{base_url.rstrip('/')}/chat/completions",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(response, Mapping):
        return json.dumps(response, ensure_ascii=False)
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], Mapping) else {}
        message = first.get("message") if isinstance(first.get("message"), Mapping) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return json.dumps(response, ensure_ascii=False)


def request_json(
    url: str,
    *,
    payload: Mapping[str, Any] | None,
    timeout_seconds: int,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return json.loads(body)


def parse_answer_json(value: object) -> tuple[dict[str, Any], bool]:
    text = clean(value)
    if not text:
        return {}, False
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
        if isinstance(parsed, dict):
            return parsed, True
    return {}, False


def parse_or_repair_answer_json(value: object) -> tuple[dict[str, Any], bool, bool, bool]:
    parsed, json_parse_ok = parse_answer_json(value)
    if is_answer_schema(parsed):
        return normalize_answer_schema(parsed), True, True, False

    repaired = repair_answer_schema_once(parsed, value)
    if is_answer_schema(repaired):
        return normalize_answer_schema(repaired), False, True, True
    return {}, False, False, False


def repair_answer_schema_once(parsed: Mapping[str, Any], raw_value: object) -> dict[str, Any]:
    candidates: list[Any] = []
    if isinstance(parsed, Mapping):
        candidates.extend(
            [
                parsed.get("parsed_answer"),
                parsed.get("answer_json"),
                parsed.get("response"),
                nested(parsed, "message", "content"),
                nested(parsed, "choices", 0, "message", "content"),
            ]
        )
    text = clean(raw_value)
    if text:
        candidates.append(text)
    for candidate in candidates:
        if isinstance(candidate, Mapping) and is_answer_schema(candidate):
            return dict(candidate)
        if isinstance(candidate, str) and candidate.strip():
            nested_parsed, _ = parse_answer_json(candidate)
            if is_answer_schema(nested_parsed):
                return nested_parsed
    return {}


def is_answer_schema(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    if "answer_shape" not in value:
        return False
    if not isinstance(value.get("citations", []), list):
        return False
    has_answer = bool(clean(value.get("answer")))
    has_abstain = bool(clean(value.get("abstain_reason")))
    return has_answer or has_abstain or clean(value.get("answer_shape")) == "KEYWORD_ECHO_FORBIDDEN"


def normalize_answer_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    citations = value.get("citations") if isinstance(value.get("citations"), list) else []
    used_terms = value.get("used_content_terms") if isinstance(value.get("used_content_terms"), list) else []
    return {
        "answer": clean(value.get("answer")),
        "answer_shape": clean(value.get("answer_shape")),
        "citations": citations,
        "abstain_reason": clean(value.get("abstain_reason")),
        "used_content_terms": [clean(term) for term in used_terms if clean(term)],
        "failure_mode_if_any": clean(value.get("failure_mode_if_any")),
    }


def llm_added_unsupported_claim(parsed_answer: Mapping[str, Any], compiled_row: Mapping[str, Any]) -> bool:
    answer = clean(parsed_answer.get("answer"))
    if not answer:
        return False
    allowed = allowed_claim_text(compiled_row)
    for number in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", answer):
        if number not in allowed:
            return True
    return False


def allowed_claim_text(compiled_row: Mapping[str, Any]) -> str:
    payload = {
        "compiled_answer": compiled_row.get("compiled_answer"),
        "evidence_object": compiled_row.get("evidence_object"),
        "content_summary": compiled_row.get("content_summary"),
    }
    return json.dumps(payload, ensure_ascii=False)


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
