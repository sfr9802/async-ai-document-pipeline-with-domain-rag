"""Probe the local LLM used for diagnostic expected-answer drafts.

This module is also the shared utility layer for the PDF/XLSX question
candidate regeneration scripts. It is intentionally local-only and
report-only: no cloud endpoint, official denominator, gold registry,
candidate artifact, baseline, production namespace, vector index, or tuning
run is opened or mutated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_BACKEND = os.environ.get("AIPIPELINE_WORKER_LLM_BACKEND", "llamacpp")
DEFAULT_LLAMACPP_BASE_URL = "http://localhost:8081/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = (
    os.environ.get("LOCAL_LLM_MODEL")
    or os.environ.get("PDF_XLSX_LLM_ANSWER_PROBE_MODEL")
    or os.environ.get("AIPIPELINE_WORKER_LLM_LLAMACPP_MODEL")
    or "gemma4-e2b-local"
)

DEFAULT_PROBE_JSON = REPORT_DIR / "local_llm_expected_answer_generation_probe_v1.json"
DEFAULT_PROBE_MD = REPORT_DIR / "local_llm_expected_answer_generation_probe_v1.md"

CANONICAL_ARTIFACTS = {
    "xlsx_policy_packet": REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json",
    "pdf_policy_packet": REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json",
    "pdf_review_input": REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl",
    "pdf_metadata": REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json",
    "pdf_layout": REPORT_DIR / "pdf_layout_gap_closure_report.json",
    "pdf_repair": REPORT_DIR / "pdf_evidence_readiness_repair_report.json",
    "human_audit_v1": REVIEW_DIR / "rag_human_audit_packet_v1.json",
    "dry_run_plan": REPORT_DIR / "report_only_tuning_dry_run_plan_v1.json",
    "transition_checklist": REPORT_DIR / "official_metric_transition_readiness_checklist_v1.json",
    "progress_doc": REPO_ROOT / "docs" / "rag-ingestion-progress.md",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_probe(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        timeout_seconds=args.timeout_seconds,
        check_endpoint=not args.skip_endpoint_check,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "local_llm_available": report["local_llm_available"],
                "base_url": report["local_llm"]["base_url"],
                "model": report["local_llm"]["model"],
                "report": report["artifact_paths"]["report_json"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=5)
    parser.add_argument("--skip-endpoint-check", action="store_true")
    parser.add_argument("--output-report", default=str(DEFAULT_PROBE_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_PROBE_MD))
    return parser.parse_args(argv)


def run_probe(
    *,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    output_report: Path = DEFAULT_PROBE_JSON,
    output_md: Path = DEFAULT_PROBE_MD,
    timeout_seconds: int = 5,
    check_endpoint: bool = True,
) -> dict[str, Any]:
    resolved = resolve_base_url(backend, base_url)
    freshness = canonical_freshness_check()
    blockers = local_llm_entry_blockers(
        backend=backend,
        base_url=resolved,
        model=model,
        check_endpoint=check_endpoint,
        timeout_seconds=timeout_seconds,
    )
    blockers.extend(f"CANONICAL_FRESHNESS:{error}" for error in freshness["errors"])
    available = not blockers
    report = {
        "schema_version": "rag_local_llm_expected_answer_generation_probe_v1",
        "generated_at": utc_timestamp(),
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if available else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "diagnostic_only": True,
        "report_only": True,
        "local_llm_available": available,
        "local_llm": {
            "backend": backend,
            "base_url": resolved,
            "model": clean(model),
            "temperature": 0,
            "strict_json_required": True,
        },
        "blockers": blockers,
        "canonical_freshness": freshness,
        "gold_candidates_created": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "external_api_used": False,
        "official_denominator_registry_opened": False,
        "tuning_run_started": False,
        "artifact_paths": {
            "report_json": repo_relative(output_report),
            "report_md": repo_relative(output_md),
        },
        "validation": {"ok": available, "errors": blockers},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_probe_markdown(report), encoding="utf-8")
    return report


def canonical_freshness_check(paths: Mapping[str, Path] | None = None) -> dict[str, Any]:
    paths = dict(paths or CANONICAL_ARTIFACTS)
    artifacts: dict[str, Any] = {}
    errors: list[str] = []
    for name, path in paths.items():
        item = {
            "path": repo_relative(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "sha256": sha256_file(path) if path.exists() and path.is_file() else "",
        }
        artifacts[name] = item
        if not path.exists() or (path.is_file() and path.stat().st_size == 0):
            errors.append(f"MISSING_OR_EMPTY:{name}")

    xlsx = read_json(paths["xlsx_policy_packet"]) if paths.get("xlsx_policy_packet", Path()).exists() else {}
    pdf_policy = read_json(paths["pdf_policy_packet"]) if paths.get("pdf_policy_packet", Path()).exists() else {}
    pdf_repair = read_json(paths["pdf_repair"]) if paths.get("pdf_repair", Path()).exists() else {}
    dry_run = read_json(paths["dry_run_plan"]) if paths.get("dry_run_plan", Path()).exists() else {}
    checklist = read_json(paths["transition_checklist"]) if paths.get("transition_checklist", Path()).exists() else {}

    xlsx_leakage_status = clean(
        xlsx.get("leakage_raw_status") or nested_mapping(xlsx, "diagnostic_metric_preview").get("leakage_status")
    )
    if xlsx_leakage_status != "PASS":
        errors.append("XLSX_LEAKAGE_STATUS_NOT_PASS")
    if int_value(xlsx.get("official_metric_input_rows")) > 0:
        errors.append("XLSX_OFFICIAL_METRIC_INPUT_ROWS_GT_0")
    if int_value(nested_mapping(xlsx, "diagnostic_metric_preview").get("clean_pass_rows")) != 23:
        errors.append("XLSX_CLEAN_PASS_ROWS_NOT_23")

    if int_value(pdf_repair.get("strict_ready_rows")) != 7:
        errors.append("PDF_EVIDENCE_STRICT_READY_ROWS_NOT_7")
    if int_value(pdf_policy.get("strict_ready_rows")) != 7:
        errors.append("PDF_POLICY_STRICT_READY_ROWS_NOT_7")
    if int_value(pdf_policy.get("official_metric_input_rows")) > 0 or int_value(pdf_repair.get("official_metric_input_rows")) > 0:
        errors.append("PDF_OFFICIAL_METRIC_INPUT_ROWS_GT_0")
    if clean(pdf_policy.get("status")) != "DIAGNOSTIC_POLICY_PACKET_READY":
        errors.append("PDF_ANSWER_CITATION_PACKET_NOT_READY")
    if bool(pdf_policy.get("promotion_evidence")):
        errors.append("PDF_PACKET_PROMOTION_EVIDENCE_TRUE")

    if int_value(dry_run.get("official_metric_input_rows")) > 0:
        errors.append("DRY_RUN_OFFICIAL_METRIC_INPUT_ROWS_GT_0")
    if dry_run.get("tuning_run_started") is not False:
        errors.append("TUNING_RUN_STARTED_NOT_FALSE")
    if int_value(checklist.get("official_metric_input_rows")) > 0:
        errors.append("CHECKLIST_OFFICIAL_METRIC_INPUT_ROWS_GT_0")

    return {
        "status": "PASS" if not errors else "FAIL_CLOSED_CANONICAL_FRESHNESS",
        "artifacts": artifacts,
        "xlsx_leakage_status": xlsx_leakage_status,
        "xlsx_clean_pass_rows": int_value(nested_mapping(xlsx, "diagnostic_metric_preview").get("clean_pass_rows")),
        "pdf_strict_ready_rows": int_value(pdf_repair.get("strict_ready_rows")),
        "official_metric_input_rows": sum(
            int_value(payload.get("official_metric_input_rows")) for payload in (xlsx, pdf_policy, pdf_repair, dry_run, checklist)
        ),
        "pdf_answer_packet_treated_as_gold": False,
        "errors": errors,
    }


def local_llm_entry_blockers(
    *,
    backend: str,
    base_url: str,
    model: str,
    check_endpoint: bool = True,
    timeout_seconds: int = 5,
) -> list[str]:
    blockers: list[str] = []
    if backend not in {"llamacpp", "openai-compatible", "ollama"}:
        blockers.append(f"unsupported local LLM backend: {backend}")
    if not clean(model):
        blockers.append("local LLM model is required")
    resolved = resolve_base_url(backend, base_url)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"}:
        blockers.append("local LLM base URL must be http(s)")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        blockers.append("external/cloud LLM endpoints are forbidden; use localhost only")
    if blockers or not check_endpoint:
        return blockers
    try:
        if backend == "ollama":
            response = request_json(f"{resolved.rstrip('/')}/api/tags", payload=None, timeout_seconds=timeout_seconds)
        else:
            response = request_json(f"{resolved.rstrip('/')}/models", payload=None, timeout_seconds=timeout_seconds)
        if not isinstance(response, (Mapping, list)):
            blockers.append("local LLM health check did not return JSON object/list")
    except Exception as exc:
        blockers.append(f"LOCAL_LLM_UNAVAILABLE: {type(exc).__name__}: {exc}")
    return blockers


def resolve_base_url(backend: str, base_url: str = "") -> str:
    if clean(base_url):
        return clean(base_url)
    if backend == "ollama":
        return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return (
        os.environ.get("OPENAI_COMPATIBLE_LOCAL_BASE_URL")
        or os.environ.get("LOCAL_LLM_BASE_URL")
        or os.environ.get("PDF_XLSX_LOCAL_LLM_BASE_URL")
        or os.environ.get("AIPIPELINE_WORKER_LLM_LLAMACPP_BASE_URL")
        or DEFAULT_LLAMACPP_BASE_URL
    )


def call_local_llm_strict_json(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 900,
    timeout_seconds: int = 120,
    llm_client: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = llm_client(prompt) if llm_client is not None else call_local_llm(
        backend=backend,
        base_url=base_url,
        model=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
    parsed = parse_strict_json_object(raw)
    return parsed, {"raw_response_sha256": sha256_text(clean(raw)), "strict_json": True}


def call_local_llm(
    *,
    backend: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> str:
    resolved = resolve_base_url(backend, base_url)
    if backend == "ollama":
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": int(max_tokens)},
        }
        response = request_json(f"{resolved.rstrip('/')}/api/generate", payload=payload, timeout_seconds=timeout_seconds)
        if isinstance(response, Mapping):
            return clean(response.get("response")) or json.dumps(response, ensure_ascii=False)
        return json.dumps(response, ensure_ascii=False)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return exactly one JSON object. No markdown or prose."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": int(max_tokens),
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    response = request_json(f"{resolved.rstrip('/')}/chat/completions", payload=payload, timeout_seconds=timeout_seconds)
    if isinstance(response, Mapping):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], Mapping) else {}
            message = first.get("message") if isinstance(first.get("message"), Mapping) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return json.dumps(response, ensure_ascii=False)


def parse_strict_json_object(value: Any) -> dict[str, Any]:
    text = clean(value)
    if not text or text.startswith("```"):
        raise ValueError("local LLM output must be a strict JSON object")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"local LLM output must be a strict JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("local LLM output must be a strict JSON object")
    return parsed


def request_json(url: str, *, payload: Mapping[str, Any] | None, timeout_seconds: int) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be object at {path}:{line_number}")
            rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def render_probe_markdown(report: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Local LLM Expected Answer Generation Probe v1",
            "",
            f"- Status: `{report.get('status')}`",
            f"- Backend: `{nested_mapping(report, 'local_llm').get('backend')}`",
            f"- Endpoint: `{nested_mapping(report, 'local_llm').get('base_url')}`",
            f"- Model: `{nested_mapping(report, 'local_llm').get('model')}`",
            f"- Local LLM available: `{str(report.get('local_llm_available')).lower()}`",
            f"- External API used: `{str(report.get('external_api_used')).lower()}`",
            f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
            f"- Tuning run started: `{str(report.get('tuning_run_started')).lower()}`",
            "",
            "## Blockers",
            *[f"- `{item}`" for item in report.get("blockers", [])],
        ]
    ) + "\n"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_relative(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, Mapping) else {}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
