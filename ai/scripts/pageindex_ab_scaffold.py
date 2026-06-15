"""Build an isolated PageIndex A/B canary bundle.

This command prepares a small markdown corpus and query manifest from the
active v4 Namu text corpus so PageIndex can be tested without touching the
production RAG index, DB state, or canonical report files.

Default mode is file-only. Passing ``--build-tree`` imports the cloned
PageIndex repo and builds a markdown tree with summaries disabled, which
should not call an LLM. PageIndex dependencies are intentionally not installed
by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_CORPUS = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined" / "rag_chunks.jsonl"
DEFAULT_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_REPORT_ROOT = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "pageindex-ab"
DEFAULT_PAGEINDEX_ROOT = REPO_ROOT / ".tmp" / "PageIndex"


@dataclass(frozen=True)
class QueryCase:
    query_id: str
    query: str
    bucket: str
    expected_page_ids: list[str]
    expected_section_ids: list[str]
    expected_chunk_ids: list[str]
    answer_type: str
    label_status: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or "canary_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.report_root) / run_id
    if run_dir.exists() and not args.overwrite:
        raise SystemExit(f"Output directory already exists: {run_dir}. Use --overwrite or a new --run-id.")
    run_dir.mkdir(parents=True, exist_ok=True)

    cases = select_cases(Path(args.gold), limit=args.limit)
    corpus_rows = read_jsonl(Path(args.corpus))
    chunks_by_id = {str(row.get("chunk_id") or ""): row for row in corpus_rows}
    docs = select_documents(
        corpus_rows,
        cases,
        chunks_by_id=chunks_by_id,
        distractor_docs=args.distractor_docs,
        max_chunks_per_doc=args.max_chunks_per_doc,
    )

    markdown_path = run_dir / "pageindex_input.md"
    query_path = run_dir / "selected_queries.jsonl"
    manifest_path = run_dir / "manifest.json"
    tree_path = run_dir / "pageindex_structure.json"

    markdown_path.write_text(render_markdown(docs), encoding="utf-8", newline="\n")
    write_jsonl(query_path, (case_to_record(c) for c in cases))

    manifest = build_manifest(
        run_id=run_id,
        run_dir=run_dir,
        args=args,
        cases=cases,
        docs=docs,
        markdown_path=markdown_path,
        query_path=query_path,
        tree_path=tree_path,
    )

    if args.build_tree:
        manifest["pageindex_tree"] = build_pageindex_tree(
            pageindex_root=Path(args.pageindex_root),
            markdown_path=markdown_path,
            tree_path=tree_path,
        )
    else:
        manifest["pageindex_tree"] = {
            "built": False,
            "reason": "pass --build-tree after installing PageIndex dependencies in an isolated environment",
        }

    write_json(manifest_path, manifest)
    print(json.dumps({
        "run_id": run_id,
        "run_dir": repo_relative(run_dir),
        "markdown": repo_relative(markdown_path),
        "queries": repo_relative(query_path),
        "manifest": repo_relative(manifest_path),
        "tree": repo_relative(tree_path) if tree_path.exists() else None,
        "case_count": len(cases),
        "document_count": len(docs),
        "chunk_count": sum(len(doc["chunks"]) for doc in docs.values()),
    }, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="rag_chunks.jsonl input.")
    parser.add_argument("--gold", default=str(DEFAULT_GOLD), help="Text gold CSV input.")
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT), help="Root for isolated PageIndex A/B outputs.")
    parser.add_argument("--run-id", default=None, help="Run directory name under --report-root.")
    parser.add_argument("--limit", type=int, default=5, help="Number of gold cases to include.")
    parser.add_argument("--distractor-docs", type=int, default=5, help="Deterministic non-gold documents to include.")
    parser.add_argument("--max-chunks-per-doc", type=int, default=20, help="Cap chunks per document, while always keeping expected chunks.")
    parser.add_argument("--pageindex-root", default=str(DEFAULT_PAGEINDEX_ROOT), help="Cloned PageIndex repo root.")
    parser.add_argument("--build-tree", action="store_true", help="Build a PageIndex markdown tree with summaries disabled.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing run directory.")
    return parser.parse_args(argv)


def select_cases(gold_path: Path, *, limit: int) -> list[QueryCase]:
    out: list[QueryCase] = []
    with gold_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            expected_chunks = split_multi(row.get("expected_chunk_ids"))
            if not expected_chunks:
                continue
            out.append(QueryCase(
                query_id=str(row.get("query_id") or row.get("id") or "").strip(),
                query=str(row.get("query") or "").strip(),
                bucket=str(row.get("bucket") or "").strip(),
                expected_page_ids=split_multi(row.get("expected_page_ids")),
                expected_section_ids=split_multi(row.get("expected_section_ids")),
                expected_chunk_ids=expected_chunks,
                answer_type=str(row.get("answer_type") or "").strip(),
                label_status=str(row.get("label_status") or "").strip(),
            ))
            if len(out) >= max(1, limit):
                break
    if not out:
        raise ValueError(f"No usable rows with expected_chunk_ids found in {gold_path}")
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: line {line_number} must be an object")
            rows.append(payload)
    return rows


def select_documents(
    corpus_rows: Sequence[Mapping[str, Any]],
    cases: Sequence[QueryCase],
    *,
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    distractor_docs: int,
    max_chunks_per_doc: int,
) -> OrderedDict[str, dict[str, Any]]:
    expected_chunk_ids = {chunk_id for case in cases for chunk_id in case.expected_chunk_ids}
    expected_doc_ids = {
        str(chunks_by_id[chunk_id].get("doc_id") or "")
        for chunk_id in expected_chunk_ids
        if chunk_id in chunks_by_id
    }
    expected_doc_ids.discard("")

    selected_doc_ids = OrderedDict((doc_id, None) for doc_id in sorted(expected_doc_ids))
    for row in corpus_rows:
        if len(selected_doc_ids) >= len(expected_doc_ids) + max(0, distractor_docs):
            break
        doc_id = str(row.get("doc_id") or "")
        if doc_id and doc_id not in selected_doc_ids:
            selected_doc_ids[doc_id] = None

    docs: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in corpus_rows:
        doc_id = str(row.get("doc_id") or "")
        if doc_id not in selected_doc_ids:
            continue
        chunk_id = str(row.get("chunk_id") or "")
        doc = docs.setdefault(doc_id, {
            "doc_id": doc_id,
            "title": str(row.get("retrieval_title") or row.get("display_title") or row.get("title") or doc_id),
            "source_url": ((row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}).get("source_url"),
            "expected": doc_id in expected_doc_ids,
            "chunks": [],
        })
        keep = len(doc["chunks"]) < max(1, max_chunks_per_doc) or chunk_id in expected_chunk_ids
        if keep:
            doc["chunks"].append(dict(row))

    missing = sorted(chunk_id for chunk_id in expected_chunk_ids if chunk_id not in chunks_by_id)
    if missing:
        raise ValueError(f"Expected chunk ids missing from corpus: {missing[:10]}")
    return docs


def render_markdown(docs: Mapping[str, Mapping[str, Any]]) -> str:
    lines: list[str] = [
        "# PageIndex A/B Canary Corpus",
        "",
        "This file is generated for an isolated PageIndex experiment.",
        "The HTML comments carry stable eval identifiers for offline scoring.",
        "",
    ]
    for doc in docs.values():
        lines.extend([
            f"## Document: {safe_heading(doc['title'])}",
            metadata_comment({
                "doc_id": doc["doc_id"],
                "source_url": doc.get("source_url"),
                "expected_document": bool(doc.get("expected")),
            }),
            "",
        ])
        for chunk in doc["chunks"]:
            section_path = chunk.get("section_path") or []
            if isinstance(section_path, list):
                section = " > ".join(str(part) for part in section_path if str(part).strip())
            else:
                section = str(section_path)
            title = section or str(chunk.get("section_id") or "section")
            lines.extend([
                f"### Section: {safe_heading(title)}",
                metadata_comment({
                    "chunk_id": chunk.get("chunk_id"),
                    "doc_id": chunk.get("doc_id"),
                    "section_id": chunk.get("section_id"),
                    "section_key": chunk.get("section_key"),
                    "section_type": chunk.get("section_type"),
                }),
                "",
                str(chunk.get("chunk_text") or "").strip(),
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def build_pageindex_tree(*, pageindex_root: Path, markdown_path: Path, tree_path: Path) -> dict[str, Any]:
    if not pageindex_root.exists():
        raise FileNotFoundError(f"PageIndex root not found: {pageindex_root}")
    sys.path.insert(0, str(pageindex_root))
    try:
        from pageindex.page_index_md import md_to_tree
    except ModuleNotFoundError as exc:
        dependency_hint = (
            "Missing PageIndex dependency. Create an isolated venv, then install "
            "the current compatible minimal set: "
            f"python -m venv {repo_relative(REPO_ROOT / '.tmp' / 'pageindex-venv')} ; "
            f"{repo_relative(REPO_ROOT / '.tmp' / 'pageindex-venv' / 'Scripts' / 'python.exe')} "
            "-m pip install litellm==1.83.7 pymupdf==1.26.4 PyPDF2==3.0.1 "
            "pyyaml==6.0.2 python-dotenv==1.0.1. "
            f"Note: {repo_relative(pageindex_root / 'requirements.txt')} currently pins "
            "python-dotenv==1.2.2, which conflicts with litellm==1.83.7."
        )
        raise RuntimeError(f"{dependency_hint}. Original import error: {exc}") from exc

    result = asyncio.run(md_to_tree(
        md_path=str(markdown_path),
        if_thinning=False,
        min_token_threshold=None,
        if_add_node_summary="no",
        summary_token_threshold=200,
        model=None,
        if_add_doc_description="no",
        if_add_node_text="yes",
        if_add_node_id="yes",
    ))
    write_json(tree_path, result)
    return {
        "built": True,
        "path": repo_relative(tree_path),
        "mode": "markdown_no_summary_no_llm",
    }


def build_manifest(
    *,
    run_id: str,
    run_dir: Path,
    args: argparse.Namespace,
    cases: Sequence[QueryCase],
    docs: Mapping[str, Mapping[str, Any]],
    markdown_path: Path,
    query_path: Path,
    tree_path: Path,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "pageindex_ab_canary_scaffold",
        "mutation_policy": {
            "db_mutation": False,
            "production_index_mutation": False,
            "canonical_report_overwrite": False,
        },
        "inputs": {
            "corpus": repo_relative(Path(args.corpus)),
            "gold": repo_relative(Path(args.gold)),
            "pageindex_root": repo_relative(Path(args.pageindex_root)),
        },
        "outputs": {
            "run_dir": repo_relative(run_dir),
            "markdown": repo_relative(markdown_path),
            "selected_queries": repo_relative(query_path),
            "pageindex_tree": repo_relative(tree_path),
        },
        "selection": {
            "case_count": len(cases),
            "document_count": len(docs),
            "chunk_count": sum(len(doc["chunks"]) for doc in docs.values()),
            "distractor_docs": int(args.distractor_docs),
            "max_chunks_per_doc": int(args.max_chunks_per_doc),
        },
        "next_commands": {
            "build_scaffold_only": (
                "python -m scripts.pageindex_ab_scaffold "
                f"--run-id {run_id} --overwrite"
            ),
            "build_pageindex_tree": (
                "python -m scripts.pageindex_ab_scaffold "
                f"--run-id {run_id} --overwrite --build-tree"
            ),
        },
        "cases": [case_to_record(case) for case in cases],
    }


def case_to_record(case: QueryCase) -> dict[str, Any]:
    return {
        "query_id": case.query_id,
        "query": case.query,
        "bucket": case.bucket,
        "expected_page_ids": case.expected_page_ids,
        "expected_section_ids": case.expected_section_ids,
        "expected_chunk_ids": case.expected_chunk_ids,
        "answer_type": case.answer_type,
        "label_status": case.label_status,
    }


def split_multi(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    for sep in ("|", ";"):
        text = text.replace(sep, ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def metadata_comment(payload: Mapping[str, Any]) -> str:
    compact = {key: value for key, value in payload.items() if value not in (None, "", [])}
    return "<!-- pageindex_ab " + json.dumps(compact, ensure_ascii=False, sort_keys=True) + " -->"


def safe_heading(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text or "untitled"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def repo_relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
