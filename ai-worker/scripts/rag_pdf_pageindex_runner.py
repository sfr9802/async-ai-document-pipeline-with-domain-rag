"""Run or fail-closed a PageIndex PDF tree generation pass.

External/cloud LLM calls are prohibited by default and are not enabled by this
wrapper. A live run requires an explicit local/open-source model configuration.
The output remains diagnostic-only and must not be used as promotion evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent
DEFAULT_PAGEINDEX_ROOT = ROOT / ".tmp" / "PageIndex"
DEFAULT_PAGEINDEX_PYTHON = ROOT / ".tmp" / "pageindex-venv" / "Scripts" / "python.exe"

LOCAL_BASE_ENV_KEYS = (
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "LITELLM_API_BASE",
    "AZURE_API_BASE",
)
BLOCKED_SECRET_ENV_KEYS = (
    "OPENAI_API_KEY",
    "CHATGPT_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "TOGETHER_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
)
LOCAL_PLACEHOLDER_API_KEYS = {
    "",
    "EMPTY",
    "empty",
    "LOCAL",
    "local",
    "DUMMY",
    "dummy",
    "NONE",
    "none",
    "not-needed",
}
LOCAL_MODEL_PREFIXES = (
    "ollama/",
    "lm_studio/",
    "hosted_vllm/",
    "openai/",
    "local/",
)
GUARDRAILS = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "xlsx_scope_excluded": True,
    "pdf_scope_only": True,
    "external_cloud_llm_run": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_not_claimed": True,
    "pdf_c7_policy_decision_applied": False,
    "retrieval_tuning_applied": False,
    "parser_expansion_applied": False,
    "official_denominator_changed": False,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = resolve_manifest(Path(args.manifest)) if args.manifest else latest_manifest()
    input_manifest = read_json(manifest_path)
    input_manifest_sha256 = sha256_file(manifest_path)
    artifact_dir = manifest_path.parent
    pageindex_root = resolve_any_path(Path(args.pageindex_root))
    pageindex_python = resolve_any_path(Path(args.python)) if args.python else default_python()
    base_url = explicit_local_base_url(args.base_url)
    canary_query_ids = dedupe([str(item).strip() for item in (args.query_id or []) if str(item).strip()])
    tree_dir = artifact_dir / "pageindex_trees"

    payload = build_run_manifest(
        input_manifest=input_manifest,
        manifest_path=manifest_path,
        input_manifest_sha256=input_manifest_sha256,
        artifact_dir=artifact_dir,
        tree_dir=tree_dir,
        pageindex_root=pageindex_root,
        pageindex_python=pageindex_python,
        allow_local_run=bool(args.allow_local_run),
        model=args.model,
        base_url=base_url,
        api_key_placeholder=args.api_key_placeholder,
        canary_query_ids=canary_query_ids,
        runner_command=redacted_runner_command(args, manifest_path, pageindex_root, pageindex_python, base_url),
        pageindex_options=pageindex_options_from_args(args),
        timeout_seconds=args.timeout_seconds,
    )
    output_path = artifact_dir / "pageindex_run_manifest.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_json(summary_for_stdout(payload, output_path))
    return 0 if payload.get("status") in {
        "SKIPPED_PAGEINDEX_RUN_NOT_REQUESTED",
        "FAIL_CLOSED_PAGEINDEX_UNAVAILABLE",
        "COMPLETED",
        "COMPLETED_WITH_FAILURES",
    } else 2


def build_run_manifest(
    *,
    input_manifest: Mapping[str, Any],
    manifest_path: Path,
    input_manifest_sha256: str,
    artifact_dir: Path,
    tree_dir: Path,
    pageindex_root: Path,
    pageindex_python: Path,
    allow_local_run: bool,
    model: str | None,
    base_url: str | None,
    api_key_placeholder: str,
    canary_query_ids: list[str],
    runner_command: list[str],
    pageindex_options: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    tree_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(input_manifest.get("run_id") or artifact_dir.name.replace("pdf_pageindex_comparison_", ""))
    query_rows = list(input_manifest.get("queries") or [])
    documents = filter_documents_for_query_ids(
        documents=list(input_manifest.get("documents") or []),
        query_rows=query_rows,
        query_ids=canary_query_ids,
    )
    run_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    local_preflight = local_run_preflight(
        allow_local_run=allow_local_run,
        model=model,
        base_url=base_url,
        pageindex_root=pageindex_root,
        pageindex_python=pageindex_python,
    )

    if not local_preflight["ready"]:
        for doc in documents:
            run_rows.append(document_skip_row(doc, local_preflight["status"], local_preflight["reason"]))
        return {
            "schema_version": "pdf_pageindex_run_manifest_v1",
            "run_id": run_id,
            "generated_at": utc_timestamp(),
            "status": local_preflight["status"],
            "track": "C",
            "phase": "PageIndex PDF tree runner",
            "source_file_type": "PDF",
            **GUARDRAILS,
            "live_pageindex_run": False,
            "local_pageindex_run": False,
            "local_open_source_run_requested": allow_local_run,
            "local_model": model,
            "local_base_url": base_url,
            "pageindex_runner_command": runner_command,
            "pageindex_options": dict(pageindex_options),
            "canary_query_ids": canary_query_ids,
            "canary_candidate_count": len(canary_query_ids) if canary_query_ids else len(query_rows),
            "pageindex_root": display_path(pageindex_root),
            "pageindex_python": display_path(pageindex_python),
            "artifact_dir": display_path(artifact_dir),
            "input_manifest": display_path(manifest_path),
            "input_manifest_sha256": input_manifest_sha256,
            "tree_dir": display_path(tree_dir),
            "documents": run_rows,
            "counts": counts_for_rows(run_rows),
            "blockers": local_preflight["blockers"],
            "warnings": warnings,
            "notes": [
                "No PageIndex tree was generated because local execution preflight did not pass.",
                "External/cloud LLM calls remain disabled.",
                "This output is diagnostic-only and is not promotion evidence.",
            ],
        }

    env = sanitized_local_env(model=model, base_url=str(base_url), api_key_placeholder=api_key_placeholder)
    run_pageindex = pageindex_root / "run_pageindex.py"
    for doc in documents:
        row = run_one_document(
            doc=doc,
            run_pageindex=run_pageindex,
            pageindex_python=pageindex_python,
            tree_dir=tree_dir,
            env=env,
            model=str(model),
            pageindex_options=pageindex_options,
            timeout_seconds=timeout_seconds,
        )
        run_rows.append(row)
        if row["status"] != "TREE_GENERATED":
            blockers.append(f"{doc.get('expected_file')}: {row['status']}")

    status = "COMPLETED" if not blockers else "COMPLETED_WITH_FAILURES"
    return {
        "schema_version": "pdf_pageindex_run_manifest_v1",
        "run_id": run_id,
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "PageIndex PDF tree runner",
        "source_file_type": "PDF",
        **GUARDRAILS,
        "live_pageindex_run": True,
        "local_pageindex_run": True,
        "local_open_source_run_requested": True,
        "local_model": model,
        "local_base_url": base_url,
        "pageindex_runner_command": runner_command,
        "pageindex_options": dict(pageindex_options),
        "canary_query_ids": canary_query_ids,
        "canary_candidate_count": len(canary_query_ids) if canary_query_ids else len(query_rows),
        "pageindex_root": display_path(pageindex_root),
        "pageindex_python": display_path(pageindex_python),
        "artifact_dir": display_path(artifact_dir),
        "input_manifest": display_path(manifest_path),
        "input_manifest_sha256": input_manifest_sha256,
        "tree_dir": display_path(tree_dir),
        "documents": run_rows,
        "counts": counts_for_rows(run_rows),
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "PageIndex output is preserved only as PDF page/section navigation evidence.",
            "bbox/table/gold-policy success is not claimed.",
            "External/cloud LLM calls remain disabled.",
        ],
    }


def local_run_preflight(
    *,
    allow_local_run: bool,
    model: str | None,
    base_url: str | None,
    pageindex_root: Path,
    pageindex_python: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not allow_local_run:
        return {
            "ready": False,
            "status": "SKIPPED_PAGEINDEX_RUN_NOT_REQUESTED",
            "reason": "Pass --allow-local-run with a local/open-source model to execute PageIndex.",
            "blockers": [],
        }
    if not pageindex_root.exists():
        blockers.append(f"PageIndex root not found: {display_path(pageindex_root)}")
    if not (pageindex_root / "run_pageindex.py").exists():
        blockers.append(f"PageIndex CLI not found: {display_path(pageindex_root / 'run_pageindex.py')}")
    if not pageindex_python.exists():
        blockers.append(f"PageIndex Python not found: {display_path(pageindex_python)}")
    if not model:
        blockers.append("--model is required for a local PageIndex run")
    elif not str(model).startswith(LOCAL_MODEL_PREFIXES):
        blockers.append(f"Model must look local/open-source; got {model!r}")
    if not base_url:
        blockers.append("--base-url or a local OPENAI_API_BASE/OPENAI_BASE_URL/LITELLM_API_BASE is required")
    elif not is_local_url(base_url):
        blockers.append(f"Base URL must be localhost/127.0.0.1/[::1]; got {base_url!r}")
    secret_keys = detected_external_secret_keys()
    if secret_keys:
        blockers.append(f"External/cloud provider key(s) detected in environment: {', '.join(secret_keys)}")
    if blockers:
        return {
            "ready": False,
            "status": "FAIL_CLOSED_PAGEINDEX_UNAVAILABLE",
            "reason": "; ".join(blockers),
            "blockers": blockers,
        }
    return {
        "ready": True,
        "status": "READY",
        "reason": "local preflight passed",
        "blockers": [],
    }


def explicit_local_base_url(cli_base_url: str | None) -> str | None:
    if cli_base_url:
        return cli_base_url.strip()
    for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "LITELLM_API_BASE"):
        value = os.environ.get(key)
        if value:
            return value.strip()
    return None


def is_local_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname
    if hostname is None:
        return False
    normalized = hostname.lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def detected_external_secret_keys() -> list[str]:
    keys: list[str] = []
    for key in BLOCKED_SECRET_ENV_KEYS:
        value = os.environ.get(key)
        if value is None:
            continue
        if value.strip() not in LOCAL_PLACEHOLDER_API_KEYS:
            keys.append(key)
    return keys


def sanitized_local_env(*, model: str | None, base_url: str, api_key_placeholder: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in BLOCKED_SECRET_ENV_KEYS:
        env.pop(key, None)
    for key in LOCAL_BASE_ENV_KEYS:
        env[key] = base_url
    env["OPENAI_API_KEY"] = api_key_placeholder
    env["PAGEINDEX_MODEL"] = model or ""
    env["PAGEINDEX_LOCAL_BASE_URL"] = base_url
    env["PAGEINDEX_EXTERNAL_CLOUD_LLM_RUN"] = "false"
    return env


def filter_documents_for_query_ids(
    *,
    documents: list[Any],
    query_rows: list[Any],
    query_ids: list[str],
) -> list[dict[str, Any]]:
    if not query_ids:
        return [dict(doc) for doc in documents if isinstance(doc, Mapping)]
    selected_ids = set(query_ids)
    query_by_id = {
        str(row.get("query_id")): row
        for row in query_rows
        if isinstance(row, Mapping) and str(row.get("query_id") or "") in selected_ids
    }
    result: list[dict[str, Any]] = []
    for doc in documents:
        if not isinstance(doc, Mapping):
            continue
        doc_query_ids = [str(item) for item in (doc.get("query_ids") or []) if str(item) in selected_ids]
        if not doc_query_ids:
            continue
        expected_pages = sorted({
            int(query_by_id[qid].get("expected_page_no"))
            for qid in doc_query_ids
            if qid in query_by_id and query_by_id[qid].get("expected_page_no") is not None
        })
        filtered = dict(doc)
        filtered["query_ids"] = doc_query_ids
        filtered["query_count"] = len(doc_query_ids)
        filtered["expected_pages"] = expected_pages
        result.append(filtered)
    return result


def run_one_document(
    *,
    doc: Mapping[str, Any],
    run_pageindex: Path,
    pageindex_python: Path,
    tree_dir: Path,
    env: Mapping[str, str],
    model: str,
    pageindex_options: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    expected_file = str(doc.get("expected_file") or "unknown.pdf")
    doc_dir = tree_dir / safe_name(Path(expected_file).stem)
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = resolve_repo_path(str(doc.get("pdf_path") or ""))
    stdout_path = doc_dir / "pageindex_stdout.txt"
    stderr_path = doc_dir / "pageindex_stderr.txt"
    if not pdf_path or not pdf_path.exists():
        return {
            **document_base_row(doc, doc_dir),
            "status": "FAIL_CLOSED_PDF_NOT_FOUND",
            "pdf_path": str(doc.get("pdf_path") or ""),
            "tree_json_path": None,
            "tree_text_path": None,
            "page_count": None,
            "node_count": 0,
            "returncode": None,
            "stdout_path": None,
            "stderr_path": None,
            "blockers": ["PDF path is unavailable or missing"],
        }

    command = [
        str(pageindex_python),
        str(run_pageindex),
        "--pdf_path",
        str(pdf_path),
        "--model",
        model,
        "--if-add-node-summary",
        "no",
        "--if-add-doc-description",
        "no",
        "--if-add-node-text",
        "no",
        "--if-add-node-id",
        "yes",
    ]
    append_optional_int_arg(command, "--toc-check-pages", pageindex_options.get("toc_check_pages"))
    append_optional_int_arg(command, "--max-pages-per-node", pageindex_options.get("max_pages_per_node"))
    append_optional_int_arg(command, "--max-tokens-per-node", pageindex_options.get("max_tokens_per_node"))
    try:
        completed = subprocess.run(
            command,
            cwd=doc_dir,
            env=dict(env),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(sanitize_pageindex_log(str(exc)) + "\n", encoding="utf-8")
        scrub_pageindex_raw_logs(doc_dir)
        return {
            **document_base_row(doc, doc_dir),
            "status": "FAIL_CLOSED_PAGEINDEX_EXECUTION_ERROR",
            "tree_json_path": None,
            "tree_text_path": None,
            "page_count": pdf_page_count(pdf_path),
            "node_count": 0,
            "returncode": None,
            "stdout_path": display_path(stdout_path),
            "stderr_path": display_path(stderr_path),
            "blockers": [str(exc)],
        }

    stdout_path.write_text(sanitize_pageindex_log(completed.stdout), encoding="utf-8")
    stderr_path.write_text(sanitize_pageindex_log(completed.stderr), encoding="utf-8")
    scrub_pageindex_raw_logs(doc_dir)
    if completed.returncode != 0:
        return {
            **document_base_row(doc, doc_dir),
            "status": "FAIL_CLOSED_PAGEINDEX_NONZERO_EXIT",
            "tree_json_path": None,
            "tree_text_path": None,
            "page_count": pdf_page_count(pdf_path),
            "node_count": 0,
            "returncode": completed.returncode,
            "stdout_path": display_path(stdout_path),
            "stderr_path": display_path(stderr_path),
            "blockers": [f"PageIndex exited with {completed.returncode}"],
        }

    tree_path = locate_tree_output(doc_dir)
    if tree_path is None:
        return {
            **document_base_row(doc, doc_dir),
            "status": "FAIL_CLOSED_TREE_OUTPUT_MISSING",
            "tree_json_path": None,
            "tree_text_path": None,
            "page_count": pdf_page_count(pdf_path),
            "node_count": 0,
            "returncode": completed.returncode,
            "stdout_path": display_path(stdout_path),
            "stderr_path": display_path(stderr_path),
            "blockers": ["PageIndex completed but no *_structure.json was found"],
        }

    canonical_tree_path = doc_dir / f"{safe_name(Path(expected_file).stem)}_structure.json"
    if tree_path.resolve() != canonical_tree_path.resolve():
        shutil.copy2(tree_path, canonical_tree_path)
    tree = json.loads(canonical_tree_path.read_text(encoding="utf-8"))
    nodes = flatten_nodes(tree.get("structure") or [])
    page_count = pdf_page_count(pdf_path)
    validation_errors = validate_nodes(nodes, page_count)
    text_path = doc_dir / f"{safe_name(Path(expected_file).stem)}_nodes.txt"
    text_path.write_text(nodes_to_text(nodes), encoding="utf-8")
    return {
        **document_base_row(doc, doc_dir),
        "status": "TREE_GENERATED" if not validation_errors else "FAIL_CLOSED_TREE_VALIDATION_ERROR",
        "tree_json_path": display_path(canonical_tree_path),
        "tree_text_path": display_path(text_path),
        "page_count": page_count,
        "node_count": len(nodes),
        "returncode": completed.returncode,
        "stdout_path": display_path(stdout_path),
        "stderr_path": display_path(stderr_path),
        "blockers": validation_errors,
    }


def document_skip_row(doc: Mapping[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        **document_base_row(doc, None),
        "status": status,
        "tree_json_path": None,
        "tree_text_path": None,
        "page_count": None,
        "node_count": 0,
        "returncode": None,
        "stdout_path": None,
        "stderr_path": None,
        "blockers": [reason] if reason else [],
    }


def document_base_row(doc: Mapping[str, Any], doc_dir: Path | None) -> dict[str, Any]:
    return {
        "expected_file": doc.get("expected_file"),
        "expected_document_version_ids": doc.get("expected_document_version_ids") or [],
        "pdf_path_found": bool(doc.get("pdf_path_found")),
        "pdf_path": doc.get("pdf_path"),
        "query_ids": doc.get("query_ids") or [],
        "query_count": doc.get("query_count") or len(doc.get("query_ids") or []),
        "expected_pages": doc.get("expected_pages") or [],
        "artifact_dir": display_path(doc_dir) if doc_dir else None,
    }


def locate_tree_output(doc_dir: Path) -> Path | None:
    candidates = sorted((doc_dir / "results").glob("*_structure.json"))
    if candidates:
        return candidates[0]
    candidates = sorted(doc_dir.glob("**/*_structure.json"))
    return candidates[0] if candidates else None


def append_optional_int_arg(command: list[str], name: str, value: Any) -> None:
    parsed = to_int(value)
    if parsed is not None:
        command.extend([name, str(parsed)])


def sanitize_pageindex_log(value: str, max_chars: int = 12000) -> str:
    if not value:
        return ""
    sanitized = re.sub(
        r"ERROR:root:Max retries reached for prompt:.*?(?=ERROR:root:Failed|\nTraceback|\Z)",
        "ERROR:root:Max retries reached for prompt: [redacted PageIndex prompt/pages]\n",
        value,
        flags=re.S,
    )
    sanitized = re.sub(r"Document pages:.*?(?=\n[A-Z][A-Za-z ]{2,}:|\nTraceback|\Z)", "[redacted PageIndex document pages]", sanitized, flags=re.S)
    sanitized = re.sub(r"<physical_index_[^>]+>.*?</physical_index_[^>]+>", "[redacted PageIndex page text]", sanitized, flags=re.S)
    sanitized = re.sub(r"(<physical_index_[^>]+>).*?(?=<physical_index_|\Z)", "[redacted PageIndex page text]\n", sanitized, flags=re.S)
    sanitized = re.sub(r"<physical_index_[^>]+>", "[physical-index-placeholder]", sanitized)
    sanitized = sanitized.replace("toc_content", "redacted_toc_var")
    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars] + "\n[truncated PageIndex diagnostic log]\n"
    return sanitized


def scrub_pageindex_raw_logs(doc_dir: Path) -> None:
    logs_dir = doc_dir / "logs"
    if not logs_dir.exists():
        return
    for path in logs_dir.glob("*.json"):
        try:
            path.unlink()
        except OSError:
            path.write_text('{"redacted": true, "reason": "PageIndex raw prompt/page log removed"}\n', encoding="utf-8")


def flatten_nodes(nodes: list[Any], depth: int = 0, parent_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("node_id") or f"{parent_id or 'root'}-{index}")
        row = {
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "title": str(node.get("title") or ""),
            "start_index": to_int(node.get("start_index")),
            "end_index": to_int(node.get("end_index")),
        }
        rows.append(row)
        rows.extend(flatten_nodes(list(node.get("nodes") or []), depth + 1, node_id))
    return rows


def validate_nodes(nodes: list[Mapping[str, Any]], page_count: int | None) -> list[str]:
    errors: list[str] = []
    for node in nodes:
        start = node.get("start_index")
        end = node.get("end_index")
        if not node.get("title"):
            errors.append(f"node {node.get('node_id')} missing title")
        if start is None or end is None:
            errors.append(f"node {node.get('node_id')} missing page range")
            continue
        if int(start) < 1 or int(end) < int(start):
            errors.append(f"node {node.get('node_id')} has invalid page range {start}-{end}")
        if page_count is not None and int(end) > page_count:
            errors.append(f"node {node.get('node_id')} ends after page_count {page_count}")
    return errors[:50]


def nodes_to_text(nodes: list[Mapping[str, Any]]) -> str:
    lines = []
    for node in nodes:
        indent = "  " * int(node.get("depth") or 0)
        lines.append(f"{indent}- p.{node.get('start_index')}-{node.get('end_index')}: {node.get('title')}")
    return "\n".join(lines) + ("\n" if lines else "")


def counts_for_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "document_count": len(rows),
        "tree_generated_count": status_counts.get("TREE_GENERATED", 0),
        "failed_or_skipped_count": len(rows) - status_counts.get("TREE_GENERATED", 0),
        "status_counts": dict(sorted(status_counts.items())),
    }


def pdf_page_count(path: Path) -> int | None:
    try:
        from PyPDF2 import PdfReader  # type: ignore

        return len(PdfReader(str(path)).pages)
    except Exception:
        try:
            from pypdf import PdfReader  # type: ignore

            return len(PdfReader(str(path)).pages)
        except Exception:
            return None


def latest_manifest() -> Path:
    candidates = sorted(
        (AI_WORKER / "eval" / "artifacts" / "eval_runs").glob(
            "pdf_pageindex_comparison_*/pageindex_pdf_input_manifest.json"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No pdf_pageindex_comparison manifest found")
    return candidates[0].resolve()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {display_path(path)}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_manifest(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    for candidate in (Path.cwd() / path, AI_WORKER / path, ROOT / path):
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / path).resolve()


def resolve_any_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    for candidate in (ROOT / path, AI_WORKER / path, Path.cwd() / path):
        if candidate.exists():
            return candidate.resolve()
    return (ROOT / path).resolve()


def resolve_repo_path(value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def default_python() -> Path:
    if DEFAULT_PAGEINDEX_PYTHON.exists():
        return DEFAULT_PAGEINDEX_PYTHON.resolve()
    return Path(sys.executable).resolve()


def safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "document"


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def redacted_runner_command(
    args: argparse.Namespace,
    manifest_path: Path,
    pageindex_root: Path,
    pageindex_python: Path,
    base_url: str | None,
) -> list[str]:
    command = [
        "python",
        "-m",
        "scripts.rag_pdf_pageindex_runner",
        "--manifest",
        display_path(manifest_path) or str(manifest_path),
        "--pageindex-root",
        display_path(pageindex_root) or str(pageindex_root),
        "--python",
        display_path(pageindex_python) or str(pageindex_python),
    ]
    if args.allow_local_run:
        command.append("--allow-local-run")
    if args.model:
        command.extend(["--model", str(args.model)])
    if base_url:
        command.extend(["--base-url", base_url])
    for query_id in args.query_id or []:
        command.extend(["--query-id", str(query_id)])
    for option_name, option_value in (
        ("--toc-check-pages", args.toc_check_pages),
        ("--max-pages-per-node", args.max_pages_per_node),
        ("--max-tokens-per-node", args.max_tokens_per_node),
    ):
        if option_value is not None:
            command.extend([option_name, str(option_value)])
    command.extend(["--timeout-seconds", str(args.timeout_seconds)])
    return command


def pageindex_options_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "toc_check_pages": args.toc_check_pages,
        "max_pages_per_node": args.max_pages_per_node,
        "max_tokens_per_node": args.max_tokens_per_node,
    }


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def summary_for_stdout(payload: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "manifest": display_path(output_path),
        "live_pageindex_run": payload.get("live_pageindex_run"),
        "local_pageindex_run": payload.get("local_pageindex_run"),
        "external_cloud_llm_run": payload.get("external_cloud_llm_run"),
        "counts": payload.get("counts"),
        "blockers": payload.get("blockers"),
    }


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=None, help="Input manifest JSON. Defaults to the latest pdf_pageindex_comparison run.")
    parser.add_argument("--pageindex-root", default=str(DEFAULT_PAGEINDEX_ROOT))
    parser.add_argument("--python", default=None, help="Python executable for PageIndex. Defaults to .tmp/pageindex-venv when available.")
    parser.add_argument("--allow-local-run", action="store_true", help="Allow PageIndex execution with a local/open-source model only.")
    parser.add_argument("--model", default=None, help="Local/open-source LiteLLM model name, e.g. ollama/qwen2.5:7b.")
    parser.add_argument("--base-url", default=None, help="Explicit localhost OpenAI-compatible/LiteLLM base URL for PageIndex.")
    parser.add_argument(
        "--api-key-placeholder",
        default="EMPTY",
        help="Non-secret local placeholder API key passed to OpenAI-compatible local endpoints.",
    )
    parser.add_argument("--query-id", action="append", default=[], help="Limit this live run to query ids for a local canary.")
    parser.add_argument("--toc-check-pages", type=int, default=None, help="Pass through to PageIndex --toc-check-pages.")
    parser.add_argument("--max-pages-per-node", type=int, default=None, help="Pass through to PageIndex --max-pages-per-node.")
    parser.add_argument("--max-tokens-per-node", type=int, default=None, help="Pass through to PageIndex --max-tokens-per-node.")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
