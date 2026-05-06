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
    )
    print_json(status)
    return 0 if status["status"] == "PASS" else 2


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
) -> dict[str, Any]:
    base_url = resolve_base_url(backend, base_url)
    output_path = output_path or inputs_path.parent / "local_llm_answers.jsonl"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = read_jsonl(inputs_path)
    if max_rows > 0:
        rows = rows[:max_rows]

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
        for index, input_row in enumerate(rows, start=1):
            prompt = build_prompt(input_row, contract_excerpt)
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
                parsed_answer, parse_ok = parse_answer_json(answer_json_raw)
            except Exception as exc:  # keep later rows diagnosable
                llm_error = f"{type(exc).__name__}: {exc}"
                answer_json_raw = json.dumps({"local_llm_error": llm_error}, ensure_ascii=False)
                parsed_answer, parse_ok = {"local_llm_error": llm_error}, False
            output_row = {
                "run_id": clean(input_row.get("run_id")) or run_id,
                "track": clean(input_row.get("track")),
                "query_id": clean(input_row.get("query_id")),
                "query": clean(input_row.get("query")),
                "expected_answer_shape": clean(input_row.get("expected_answer_shape")),
                "answer_json_raw": answer_json_raw,
                "parsed_answer": parsed_answer,
                "parse_ok": parse_ok,
                "local_llm_error": llm_error,
                "local_llm_run": True,
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
        "backend": backend,
        "model": model,
        "base_url": base_url,
        "ollama_base_url": base_url if backend == "ollama" else DEFAULT_OLLAMA_BASE_URL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "row_count": len(output_rows),
        "parse_ok_count": sum(1 for row in output_rows if row["parse_ok"]),
        "invalid_json_answer_count": sum(1 for row in output_rows if not row["parse_ok"]),
        "local_llm_run": True,
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
                "expected_answer_text": input_row.get("expected_answer_text"),
                "must_contain_terms": input_row.get("must_contain_terms"),
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


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
