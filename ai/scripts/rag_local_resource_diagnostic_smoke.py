"""Report-only local DB and local LLM diagnostic smoke.

This script verifies that the local PostgreSQL/RAG schemas and the local
OpenAI-compatible llama.cpp endpoint are reachable. It does not mutate
databases, indexes, official denominators, or candidate artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from scripts.doctor import check_postgres, check_schemas  # noqa: E402


DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_LLAMACPP_BASE_URL = "http://localhost:8081/v1"
DEFAULT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "local_resource_diagnostic_smoke_report.json"
DEFAULT_MD = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "local_resource_diagnostic_smoke_report.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(
        db_dsn=args.db_dsn,
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
        timeout_seconds=args.timeout_seconds,
    )
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    write_json(json_path, report)
    write_text(md_path, render_md(report))
    print(json.dumps({"status": report["status"], "json": repo_relative(json_path), "md": repo_relative(md_path)}, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dsn", default=os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN)
    parser.add_argument("--llm-base-url", default=os.environ.get("PDF_XLSX_LOCAL_LLM_BASE_URL") or DEFAULT_LLAMACPP_BASE_URL)
    parser.add_argument("--llm-model", default=os.environ.get("PDF_XLSX_LLM_ANSWER_PROBE_MODEL") or "")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    return parser.parse_args(argv)


def run_smoke(*, db_dsn: str, llm_base_url: str, llm_model: str, timeout_seconds: int) -> dict[str, Any]:
    postgres = check_postgres(db_dsn)
    schemas = check_schemas(db_dsn) if postgres.status == "PASS" else None
    llm = check_local_llm(llm_base_url, llm_model, timeout_seconds=timeout_seconds)
    status = "PASS"
    warnings: list[str] = []
    blockers: list[str] = []
    if postgres.status != "PASS":
        blockers.append("local PostgreSQL is not reachable")
    if schemas is None or schemas.status != "PASS":
        blockers.append("local DB schemas are not ready")
    if llm["status"] != "PASS":
        blockers.append("local llama.cpp chat smoke failed")
    if blockers:
        status = "FAIL"
    return {
        "schema_version": "rag_local_resource_diagnostic_smoke_v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "external_live_llm_run": False,
        "official_denominator_registry_changed": False,
        "db_mutation": False,
        "production_index_mutation": False,
        "broad_indexing": False,
        "local_db": {
            "postgres_status": postgres.status,
            "postgres_summary": postgres.summary,
            "schemas_status": schemas.status if schemas else "SKIPPED",
            "schemas_summary": schemas.summary if schemas else "postgres_check_failed",
            "dsn": redact_dsn(db_dsn),
        },
        "local_llm": llm,
        "warnings": warnings,
        "blockers": blockers,
    }


def check_local_llm(base_url: str, model: str, *, timeout_seconds: int) -> dict[str, Any]:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return {"status": "FAIL", "error": "local LLM base URL must be localhost only", "base_url": base_url}
    normalized = base_url.rstrip("/")
    try:
        models_payload = http_json("GET", f"{normalized}/models", timeout_seconds=timeout_seconds)
    except Exception as exc:
        return {"status": "FAIL", "base_url": normalized, "error": f"{type(exc).__name__}: {exc}"}
    model_id = model or first_model_id(models_payload) or "gemma4-e2b-local"
    messages = [
        {"role": "system", "content": "Return only compact JSON."},
        {"role": "user", "content": 'Return {"status":"PASS","resource":"local_llm","scope":"diagnostic_only"} exactly.'},
    ]
    started = time.monotonic()
    try:
        chat_payload = http_json(
            "POST",
            f"{normalized}/chat/completions",
            timeout_seconds=timeout_seconds,
            payload={"model": model_id, "messages": messages, "temperature": 0, "max_tokens": 80},
        )
    except Exception as exc:
        return {
            "status": "FAIL",
            "base_url": normalized,
            "model": model_id,
            "models_available": model_count(models_payload),
            "error": f"{type(exc).__name__}: {exc}",
        }
    content = (((chat_payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    return {
        "status": "PASS",
        "base_url": normalized,
        "model": model_id,
        "models_available": model_count(models_payload),
        "chat_latency_ms": round((time.monotonic() - started) * 1000, 2),
        "response_preview": content[:160],
        "local_llm_run": True,
    }


def http_json(method: str, url: str, *, timeout_seconds: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def first_model_id(payload: dict[str, Any]) -> str:
    for key in ("data", "models"):
        values = payload.get(key)
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, dict):
                return str(first.get("id") or first.get("model") or first.get("name") or "")
    return ""


def model_count(payload: dict[str, Any]) -> int:
    for key in ("data", "models"):
        values = payload.get(key)
        if isinstance(values, list):
            return len(values)
    return 0


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Local Resource Diagnostic Smoke Report",
        "",
        f"- Status: `{report['status']}`.",
        "- Role: diagnostic-only local resource availability check.",
        "- External live LLM run: `false`.",
        "- Production index mutation: `false`.",
        "- Official denominator registry changed: `false`.",
        "",
        "## DB",
        "",
        f"- PostgreSQL: `{report['local_db']['postgres_status']}` - {report['local_db']['postgres_summary']}",
        f"- Schemas: `{report['local_db']['schemas_status']}` - {report['local_db']['schemas_summary']}",
        "",
        "## Local LLM",
        "",
        f"- Status: `{report['local_llm']['status']}`.",
        f"- Base URL: `{report['local_llm'].get('base_url', '')}`.",
        f"- Model: `{report['local_llm'].get('model', '')}`.",
        f"- Models available: `{report['local_llm'].get('models_available', 0)}`.",
        "",
    ]
    if report["blockers"]:
        lines.extend(["## Blockers", ""])
        for blocker in report["blockers"]:
            lines.append(f"- {blocker}")
        lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def redact_dsn(value: str) -> str:
    return " ".join("password=<redacted>" if part.startswith("password=") else part for part in value.split())


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
