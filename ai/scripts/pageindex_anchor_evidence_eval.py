"""Evaluate PageIndex anchor-to-evidence expansion.

This diagnostic starts after an anchor chunk is known. It asks whether the
PageIndex heading tree can expand that anchor into answerable evidence by
adding document and section structure plus nearby sibling chunks.

It does not call live PageIndex agents, mutate DB state, or alter production
indexes. Treat the output as a diagnostic for context/evidence assembly, not as
retrieval quality proof.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from scripts.pageindex_ab_eval import (  # noqa: E402
    extract_comment_metadata,
    resolve_manifest_path,
    strip_pageindex_markup,
)


DEFAULT_RUN_DIR = AI_WORKER_ROOT / "eval" / "reports" / "pageindex-ab" / "canary_smoke"
DEFAULT_OUTPUT_DIR_NAME = "anchor_evidence"
SUMMARY_COVERAGE_THRESHOLD = 0.25


@dataclass(frozen=True)
class TreeLeaf:
    order: int
    chunk_id: str
    doc_id: str
    section_id: str
    section: str
    section_type: str
    doc_title: str
    node_id: str
    line_num: int | None
    text: str


@dataclass(frozen=True)
class QueryCase:
    query_id: str
    query: str
    bucket: str
    expected_page_ids: tuple[str, ...]
    expected_section_ids: tuple[str, ...]
    expected_chunk_ids: tuple[str, ...]
    expected_answer_summary: str
    must_contain_terms: tuple[str, ...]
    must_not_contain_terms: tuple[str, ...]
    answer_type: str
    label_status: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir)
    output_dir = Path(args.output_dir) if args.output_dir else run_dir / DEFAULT_OUTPUT_DIR_NAME
    manifest = read_json(run_dir / "manifest.json")
    tree_payload = read_json(run_dir / "pageindex_structure.json")
    selected_rows = read_jsonl(run_dir / "selected_queries.jsonl")
    gold_rows = read_gold_csv(resolve_manifest_path(manifest, "gold"))
    leaves = flatten_leaves(tree_payload)
    leaves_by_chunk = {leaf.chunk_id: leaf for leaf in leaves}
    leaves_by_doc = group_by_doc(leaves)

    cases = build_cases(selected_rows, gold_rows)
    row_outputs: list[dict[str, Any]] = []
    for case in cases:
        row_outputs.append(evaluate_case(
            case,
            leaves_by_chunk=leaves_by_chunk,
            leaves_by_doc=leaves_by_doc,
            sibling_window=args.sibling_window,
        ))

    report = build_report(
        run_dir=run_dir,
        output_dir=output_dir,
        manifest=manifest,
        cases=cases,
        leaves=leaves,
        rows=row_outputs,
        sibling_window=args.sibling_window,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "anchor_evidence_rows.jsonl"
    report_path = output_dir / "anchor_evidence_report.json"
    markdown_path = output_dir / "anchor_evidence_report.md"
    write_jsonl(rows_path, row_outputs)
    write_json(report_path, report)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "output_dir": repo_relative(output_dir),
        "query_count": report["query_count"],
        "pageindex_structural_gain_count": report["variant_aggregates"]
        .get("pageindex_anchor_with_structure", {})
        .get("newly_answerable_vs_anchor_only_count"),
        "pageindex_window_gain_count": report["variant_aggregates"]
        .get("pageindex_doc_window", {})
        .get("newly_answerable_vs_anchor_only_count"),
        "report": repo_relative(report_path),
        "rows": repo_relative(rows_path),
        "markdown": repo_relative(markdown_path),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--sibling-window",
        type=int,
        default=2,
        help="Number of previous/next PageIndex leaf siblings to include in doc-window expansion.",
    )
    return parser.parse_args(argv)


def evaluate_case(
    case: QueryCase,
    *,
    leaves_by_chunk: Mapping[str, TreeLeaf],
    leaves_by_doc: Mapping[str, Sequence[TreeLeaf]],
    sibling_window: int,
) -> dict[str, Any]:
    anchor = first_existing_leaf(case.expected_chunk_ids, leaves_by_chunk)
    if anchor is None:
        return {
            "query_id": case.query_id,
            "query": case.query,
            "bucket": case.bucket,
            "status": "missing_anchor",
            "expected_chunk_ids": list(case.expected_chunk_ids),
            "variants": {},
        }

    variants = {
        "anchor_chunk_text": [anchor],
        "pageindex_anchor_with_structure": [anchor],
        "pageindex_section_window": section_window(anchor, leaves_by_doc),
        "pageindex_doc_window": doc_window(anchor, leaves_by_doc, sibling_window=sibling_window),
    }
    evaluated = {
        name: evaluate_context(
            case,
            leaves=items,
            include_structure=name != "anchor_chunk_text",
        )
        for name, items in variants.items()
    }
    anchor_answerable = evaluated["anchor_chunk_text"]["answerable_from_context"]
    for name, payload in evaluated.items():
        payload["newly_answerable_vs_anchor_only"] = (
            name != "anchor_chunk_text"
            and payload["answerable_from_context"]
            and not anchor_answerable
        )
        payload["coverage_gain_vs_anchor_only"] = round(
            float(payload["summary_coverage_ratio"])
            - float(evaluated["anchor_chunk_text"]["summary_coverage_ratio"]),
            6,
        )

    best_variant = max(
        evaluated.items(),
        key=lambda item: (
            bool(item[1]["answerable_from_context"]),
            float(item[1]["summary_coverage_ratio"]),
            bool(item[1]["must_contain_pass"]),
        ),
    )[0]
    return {
        "query_id": case.query_id,
        "query": case.query,
        "bucket": case.bucket,
        "status": "evaluated",
        "anchor": leaf_summary(anchor),
        "expected_page_ids": list(case.expected_page_ids),
        "expected_section_ids": list(case.expected_section_ids),
        "expected_chunk_ids": list(case.expected_chunk_ids),
        "expected_answer_summary": case.expected_answer_summary,
        "must_contain_terms": list(case.must_contain_terms),
        "best_variant": best_variant,
        "variants": evaluated,
    }


def evaluate_context(
    case: QueryCase,
    *,
    leaves: Sequence[TreeLeaf],
    include_structure: bool,
) -> dict[str, Any]:
    text = "\n\n".join(render_leaf_context(leaf, include_structure=include_structure) for leaf in leaves)
    expected_chunks = set(case.expected_chunk_ids)
    expected_sections = set(case.expected_section_ids)
    expected_pages = set(case.expected_page_ids)
    chunk_ids = [leaf.chunk_id for leaf in leaves]
    section_ids = [leaf.section_id for leaf in leaves if leaf.section_id]
    doc_ids = [leaf.doc_id for leaf in leaves if leaf.doc_id]

    summary_tokens = expected_summary_tokens(case.expected_answer_summary)
    matched_summary_tokens = [token for token in summary_tokens if contains_text(text, token)]
    missing_summary_tokens = [token for token in summary_tokens if token not in matched_summary_tokens]
    matched_must = [term for term in case.must_contain_terms if contains_text(text, term)]
    missing_must = [term for term in case.must_contain_terms if term not in matched_must]
    must_not_violations = [term for term in case.must_not_contain_terms if contains_text(text, term)]
    summary_coverage = safe_ratio(len(matched_summary_tokens), len(summary_tokens))
    must_contain_pass = not case.must_contain_terms or not missing_must
    must_not_pass = not must_not_violations
    expected_chunk_present = bool(expected_chunks.intersection(chunk_ids))
    answerable = bool(
        expected_chunk_present
        and must_not_pass
        and (must_contain_pass or summary_coverage >= SUMMARY_COVERAGE_THRESHOLD)
    )
    return {
        "answerable_from_context": answerable,
        "expected_chunk_present": expected_chunk_present,
        "expected_section_present": bool(expected_sections.intersection(section_ids)),
        "expected_page_present": bool(expected_pages.intersection(doc_ids)),
        "chunk_count": len(leaves),
        "char_count": len(text),
        "chunk_ids": chunk_ids,
        "section_ids": section_ids,
        "doc_ids": sorted(set(doc_ids)),
        "summary_coverage_ratio": summary_coverage,
        "matched_summary_tokens": matched_summary_tokens,
        "missing_summary_tokens": missing_summary_tokens,
        "must_contain_pass": must_contain_pass,
        "matched_must_contain_terms": matched_must,
        "missing_must_contain_terms": missing_must,
        "must_not_pass": must_not_pass,
        "must_not_violations": must_not_violations,
        "context_preview": text[:800],
    }


def section_window(anchor: TreeLeaf, leaves_by_doc: Mapping[str, Sequence[TreeLeaf]]) -> list[TreeLeaf]:
    doc_leaves = list(leaves_by_doc.get(anchor.doc_id, ()))
    if anchor.section_id:
        section_matches = [leaf for leaf in doc_leaves if leaf.section_id == anchor.section_id]
        if section_matches:
            return section_matches
    return [leaf for leaf in doc_leaves if leaf.section == anchor.section] or [anchor]


def doc_window(
    anchor: TreeLeaf,
    leaves_by_doc: Mapping[str, Sequence[TreeLeaf]],
    *,
    sibling_window: int,
) -> list[TreeLeaf]:
    doc_leaves = list(leaves_by_doc.get(anchor.doc_id, ()))
    index = next((idx for idx, leaf in enumerate(doc_leaves) if leaf.chunk_id == anchor.chunk_id), -1)
    if index < 0:
        return [anchor]
    left = max(0, index - max(0, sibling_window))
    right = min(len(doc_leaves), index + max(0, sibling_window) + 1)
    return doc_leaves[left:right]


def first_existing_leaf(
    chunk_ids: Sequence[str],
    leaves_by_chunk: Mapping[str, TreeLeaf],
) -> TreeLeaf | None:
    for chunk_id in chunk_ids:
        leaf = leaves_by_chunk.get(chunk_id)
        if leaf:
            return leaf
    return None


def flatten_leaves(tree_payload: Mapping[str, Any]) -> list[TreeLeaf]:
    leaves: list[TreeLeaf] = []
    order = 0

    def walk(nodes: Sequence[Mapping[str, Any]], current_doc: tuple[str, str]) -> None:
        nonlocal order
        for node in nodes:
            title = clean(node.get("title"))
            text = clean(node.get("text"))
            meta = extract_comment_metadata(text)
            doc_id, doc_title = current_doc
            if meta.get("doc_id") and not meta.get("chunk_id"):
                doc_id = clean(meta.get("doc_id"))
                doc_title = title.removeprefix("Document: ").strip()
            if meta.get("chunk_id"):
                order += 1
                leaves.append(TreeLeaf(
                    order=order,
                    chunk_id=clean(meta.get("chunk_id")),
                    doc_id=clean(meta.get("doc_id") or doc_id),
                    section_id=clean(meta.get("section_id")),
                    section=title.removeprefix("Section: ").strip(),
                    section_type=clean(meta.get("section_type")),
                    doc_title=doc_title,
                    node_id=clean(node.get("node_id")),
                    line_num=to_int(node.get("line_num")),
                    text=strip_pageindex_markup(text),
                ))
            children = node.get("nodes") or []
            if isinstance(children, list):
                walk(children, (doc_id, doc_title))

    roots = tree_payload.get("structure") or []
    if not isinstance(roots, list):
        raise ValueError("PageIndex structure must contain a list field named 'structure'")
    walk(roots, ("", ""))
    if not leaves:
        raise ValueError("No PageIndex leaf nodes with chunk metadata found")
    return leaves


def group_by_doc(leaves: Sequence[TreeLeaf]) -> dict[str, list[TreeLeaf]]:
    out: dict[str, list[TreeLeaf]] = {}
    for leaf in leaves:
        out.setdefault(leaf.doc_id, []).append(leaf)
    for doc_leaves in out.values():
        doc_leaves.sort(key=lambda leaf: leaf.order)
    return out


def build_cases(
    selected_rows: Sequence[Mapping[str, Any]],
    gold_rows: Mapping[str, Mapping[str, str]],
) -> list[QueryCase]:
    cases: list[QueryCase] = []
    for selected in selected_rows:
        query_id = clean(selected.get("query_id") or selected.get("id"))
        gold = gold_rows.get(query_id, {})
        cases.append(QueryCase(
            query_id=query_id,
            query=clean(selected.get("query") or gold.get("query")),
            bucket=clean(selected.get("bucket") or gold.get("bucket")),
            expected_page_ids=tuple(clean_list(selected.get("expected_page_ids") or gold.get("expected_page_ids"))),
            expected_section_ids=tuple(clean_list(selected.get("expected_section_ids") or gold.get("expected_section_ids"))),
            expected_chunk_ids=tuple(clean_list(selected.get("expected_chunk_ids") or gold.get("expected_chunk_ids"))),
            expected_answer_summary=clean(gold.get("expected_answer_summary")),
            must_contain_terms=tuple(split_terms(gold.get("must_contain_terms"))),
            must_not_contain_terms=tuple(split_terms(gold.get("must_not_contain_terms"))),
            answer_type=clean(selected.get("answer_type") or gold.get("answer_type")),
            label_status=clean(selected.get("label_status") or gold.get("label_status")),
        ))
    if not cases:
        raise ValueError("No selected query rows found")
    return cases


def build_report(
    *,
    run_dir: Path,
    output_dir: Path,
    manifest: Mapping[str, Any],
    cases: Sequence[QueryCase],
    leaves: Sequence[TreeLeaf],
    rows: Sequence[Mapping[str, Any]],
    sibling_window: int,
) -> dict[str, Any]:
    variant_names = [
        "anchor_chunk_text",
        "pageindex_anchor_with_structure",
        "pageindex_section_window",
        "pageindex_doc_window",
    ]
    aggregates = {
        name: aggregate_variant(rows, name, anchor_variant="anchor_chunk_text")
        for name in variant_names
    }
    missing_anchor = [row["query_id"] for row in rows if row.get("status") == "missing_anchor"]
    pageindex_gain_count = max(
        aggregates["pageindex_anchor_with_structure"]["newly_answerable_vs_anchor_only_count"],
        aggregates["pageindex_section_window"]["newly_answerable_vs_anchor_only_count"],
        aggregates["pageindex_doc_window"]["newly_answerable_vs_anchor_only_count"],
    )
    return {
        "schema_version": "pageindex_anchor_evidence_report_v1",
        "status": "PASS_WITH_WARNINGS" if missing_anchor else "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "evaluation_mode": "anchor_to_structural_evidence_expansion",
        "run_dir": repo_relative(run_dir),
        "output_dir": repo_relative(output_dir),
        "source_manifest": repo_relative(run_dir / "manifest.json"),
        "source_pageindex_structure": repo_relative(run_dir / "pageindex_structure.json"),
        "source_selected_queries": repo_relative(run_dir / "selected_queries.jsonl"),
        "source_gold": manifest.get("inputs", {}).get("gold"),
        "mutation_policy": {
            "db_mutation": False,
            "production_index_mutation": False,
            "canonical_report_overwrite": False,
            "live_pageindex_agent_run": False,
            "llm_call_run": False,
        },
        "query_count": len(cases),
        "pageindex_leaf_count": len(leaves),
        "sibling_window": sibling_window,
        "summary_coverage_threshold": SUMMARY_COVERAGE_THRESHOLD,
        "missing_anchor_query_ids": missing_anchor,
        "variant_aggregates": aggregates,
        "pageindex_structural_or_window_gain_count": pageindex_gain_count,
        "interpretation": (
            "A gain means the anchor chunk alone was not deterministically answerable, "
            "but PageIndex-derived structure or sibling expansion made it answerable "
            "under the same R7-style deterministic checks."
        ),
        "caveat": (
            "This tests context/evidence expansion after a known anchor. It does not "
            "measure live PageIndex retrieval-agent quality."
        ),
    }


def aggregate_variant(
    rows: Sequence[Mapping[str, Any]],
    variant_name: str,
    *,
    anchor_variant: str,
) -> dict[str, Any]:
    evaluated = [row for row in rows if row.get("status") == "evaluated"]
    payloads = [row.get("variants", {}).get(variant_name, {}) for row in evaluated]
    anchor_payloads = [row.get("variants", {}).get(anchor_variant, {}) for row in evaluated]
    answerable = [payload for payload in payloads if payload.get("answerable_from_context")]
    newly_answerable = [
        payload
        for payload, anchor in zip(payloads, anchor_payloads)
        if payload.get("answerable_from_context") and not anchor.get("answerable_from_context")
    ]
    coverage_values = [float(payload.get("summary_coverage_ratio") or 0.0) for payload in payloads]
    chunk_counts = [int(payload.get("chunk_count") or 0) for payload in payloads]
    missing_terms = Counter(
        term
        for payload in payloads
        for term in list(payload.get("missing_must_contain_terms") or [])
    )
    return {
        "evaluated_count": len(payloads),
        "answerable_count": len(answerable),
        "answerable_rate": safe_ratio(len(answerable), len(payloads)),
        "newly_answerable_vs_anchor_only_count": len(newly_answerable),
        "must_contain_pass_count": sum(1 for payload in payloads if payload.get("must_contain_pass")),
        "expected_chunk_present_count": sum(1 for payload in payloads if payload.get("expected_chunk_present")),
        "summary_coverage_avg": round(sum(coverage_values) / len(coverage_values), 6) if coverage_values else None,
        "chunk_count_avg": round(sum(chunk_counts) / len(chunk_counts), 3) if chunk_counts else None,
        "top_missing_must_terms": [
            {"term": term, "count": count}
            for term, count in missing_terms.most_common(10)
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    variants = report.get("variant_aggregates", {})
    lines = [
        "# PageIndex Anchor Evidence Expansion",
        "",
        f"- query_count: **{report.get('query_count')}**",
        f"- pageindex_leaf_count: **{report.get('pageindex_leaf_count')}**",
        f"- evaluation_mode: `{report.get('evaluation_mode')}`",
        f"- sibling_window: **{report.get('sibling_window')}**",
        "",
        "## Variant Metrics",
        "",
        "| variant | answerable | newly answerable vs anchor | must_contain pass | avg summary coverage | avg chunks |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, payload in variants.items():
        lines.append(
            "| {name} | {answerable}/{total} | {newly} | {must_pass} | {coverage:.4f} | {chunks:.3f} |".format(
                name=name,
                answerable=payload.get("answerable_count", 0),
                total=payload.get("evaluated_count", 0),
                newly=payload.get("newly_answerable_vs_anchor_only_count", 0),
                must_pass=payload.get("must_contain_pass_count", 0),
                coverage=float(payload.get("summary_coverage_avg") or 0.0),
                chunks=float(payload.get("chunk_count_avg") or 0.0),
            )
        )
    lines.extend([
        "",
        "## Caveat",
        "",
        str(report.get("caveat") or ""),
        "",
    ])
    return "\n".join(lines)


def render_leaf_context(leaf: TreeLeaf, *, include_structure: bool) -> str:
    if not include_structure:
        return leaf.text
    return "\n".join([
        f"제목: {leaf.doc_title}",
        f"섹션: {leaf.section}",
        f"섹션타입: {leaf.section_type}",
        "",
        leaf.text,
    ]).strip()


def leaf_summary(leaf: TreeLeaf) -> dict[str, Any]:
    return {
        "chunk_id": leaf.chunk_id,
        "doc_id": leaf.doc_id,
        "section_id": leaf.section_id,
        "doc_title": leaf.doc_title,
        "section": leaf.section,
        "node_id": leaf.node_id,
        "line_num": leaf.line_num,
    }


def expected_summary_tokens(summary: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", summary.lower())
    stopwords = {"으로", "하는", "있다", "이다", "한다", "대한", "중", "및"}
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) < 2 or token in stopwords:
            continue
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def split_terms(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;|]", text) if part.strip()]


def clean_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    if not text:
        return []
    normalized = text.replace("|", ";").replace(",", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def contains_text(haystack: str, needle: str) -> bool:
    text = normalize_text(haystack)
    term = normalize_text(needle)
    if not term:
        return True
    return term in text or term.replace(" ", "") in text.replace(" ", "")


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower())


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 6)


def read_gold_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            clean(row.get("query_id")): row
            for row in csv.DictReader(handle)
            if clean(row.get("query_id"))
        }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: line {line_number} must be a JSON object")
            rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def repo_relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
