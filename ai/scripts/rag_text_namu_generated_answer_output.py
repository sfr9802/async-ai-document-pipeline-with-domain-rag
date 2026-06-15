"""Generate TEXT/Namu diagnostic generated-answer review input JSONL.

This wrapper is intentionally diagnostic-only. It uses the existing
``ExtractiveGenerator`` against source-bound TEXT/Namu review-pack evidence so
answer/citation reviewers have concrete generated answer text, cited chunks,
and provenance to inspect. It does not run retrieval, mutate indexes, open
official denominators, or compute official metrics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from app.capabilities.rag.generation import ExtractiveGenerator, RetrievedChunk  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_TEXT_REVIEW_PACK = (
    REVIEW_DIR
    / "text_namu_v2_gold_review"
    / "text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv"
)
DEFAULT_NORMALIZATION_REPORT = REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.json"
DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_gold_policy_applied_decisions_v1.json"
DEFAULT_JSONL = REPORT_DIR / "rag_text_namu_generated_answer_review_input.jsonl"
DEFAULT_REPORT_JSON = REPORT_DIR / "rag_text_namu_generated_answer_review_input_report.json"
DEFAULT_REPORT_MD = REPORT_DIR / "rag_text_namu_generated_answer_review_input_report.md"

SCHEMA_VERSION = "rag_text_namu_generated_answer_review_input_row_v1"
REPORT_SCHEMA_VERSION = "rag_text_namu_generated_answer_review_input_report_v1"
PHASE = "TEXT_NAMU_V2_GENERATED_ANSWER_REVIEW_INPUT"
PROMPT_TEMPLATE = """Answer the query using only the provided source-bound chunk text.
Return a concise grounded answer and cite the supporting chunk id."""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        text_review_pack=Path(args.text_review_pack),
        normalization_report=Path(args.normalization_report),
        applied_decisions=Path(args.applied_decisions),
        output_jsonl=Path(args.output_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print_json(
        {
            "status": report["status"],
            "jsonl": report["artifact_paths"]["generated_answer_jsonl"],
            "report": report["artifact_paths"]["report_json"],
            "generated_answer_rows": report["generated_answer_rows"],
            "missing_generated_answer_rows": report["missing_generated_answer_rows"],
            "official_metric_input_rows": report["official_metric_input_rows"],
        }
    )
    return 0 if report["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-review-pack", default=str(DEFAULT_TEXT_REVIEW_PACK))
    parser.add_argument("--normalization-report", default=str(DEFAULT_NORMALIZATION_REPORT))
    parser.add_argument("--applied-decisions", default=str(DEFAULT_APPLIED_DECISIONS))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def run_generation(
    *,
    text_review_pack: Path,
    normalization_report: Path,
    applied_decisions: Path | None = None,
    output_jsonl: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    run_id = utc_run_id()
    review_rows, review_columns = read_csv_if_exists(text_review_pack)
    normalization = read_json_if_exists(normalization_report)
    applied = read_json_if_exists(applied_decisions) if applied_decisions is not None else {}
    text = ((normalization.get("tracks") or {}).get("text_namu_v2") or {})
    applied_text = (((applied.get("applied_decisions") or {}).get("text_namu_v2_unresolved_carry_forward")) or {})
    candidate_ids = clean_list(text.get("proposed_official_candidate_query_ids"))
    review_by_id = {clean(row.get("query_id")): row for row in review_rows if clean(row.get("query_id"))}

    generated_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, str]] = []
    generator = ExtractiveGenerator(excerpt_chars=400)
    prompt_sha = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    review_pack_sha = sha256_if_exists(text_review_pack)

    for query_id in candidate_ids:
        source_row = review_by_id.get(query_id)
        if not source_row:
            missing_rows.append({"query_id": query_id, "reason": "review_pack_row_missing"})
            continue
        blockers = source_row_blockers(source_row)
        if blockers:
            missing_rows.append({"query_id": query_id, "reason": "; ".join(blockers)})
            continue
        generated_rows.append(
            build_generated_row(
                source_row=source_row,
                generator=generator,
                generated_at=generated_at,
                run_id=run_id,
                prompt_sha=prompt_sha,
                text_review_pack=text_review_pack,
                review_pack_sha=review_pack_sha,
            )
        )

    contract_errors = contract_errors_by_query(generated_rows)
    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        text_review_pack=text_review_pack,
        review_pack_sha=review_pack_sha,
        review_columns=review_columns,
        normalization_report=normalization_report,
        normalization=normalization,
        text=text,
        applied_decisions=applied_decisions,
        applied_text=applied_text,
        candidate_ids=candidate_ids,
        generated_rows=generated_rows,
        missing_rows=missing_rows,
        contract_errors=contract_errors,
        output_jsonl=output_jsonl,
        output_report=output_report,
        output_md=output_md,
        prompt_sha=prompt_sha,
    )

    if generated_rows:
        write_jsonl(output_jsonl, generated_rows)
        report["artifact_paths"]["generated_answer_jsonl_sha256"] = sha256_file(output_jsonl)
    else:
        report["artifact_paths"]["generated_answer_jsonl_sha256"] = None
    write_json(output_report, report)
    write_text(output_md, render_markdown(report))
    return report


def build_generated_row(
    *,
    source_row: Mapping[str, str],
    generator: ExtractiveGenerator,
    generated_at: str,
    run_id: str,
    prompt_sha: str,
    text_review_pack: Path,
    review_pack_sha: str | None,
) -> dict[str, Any]:
    query_id = clean(source_row.get("query_id"))
    query = clean(source_row.get("query"))
    chunk_ids = split_ids(source_row.get("expected_chunk_ids"))
    page_ids = split_ids(source_row.get("expected_page_ids"))
    section_ids = split_ids(source_row.get("expected_section_ids"))
    evidence_text = clean(source_row.get("source_evidence_quote"))
    source_url = clean(source_row.get("source_url"))
    section_path = clean(source_row.get("expected_section_path"))
    page_title = clean(source_row.get("expected_page_title"))
    chunk_sha = clean(source_row.get("chunk_text_sha256"))
    source_locator = clean(source_row.get("source_locator"))
    chunks = [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=page_ids[0] if page_ids else clean(source_row.get("expected_document_ids")) or "text_namu_v2_source",
            section=section_path or (section_ids[0] if section_ids else "source_bound_chunk"),
            text=evidence_text,
            score=1.0,
            title=page_title or None,
            section_path=section_path or None,
            metadata_json={
                "page_id": page_ids[0] if page_ids else None,
                "section_id": section_ids[0] if section_ids else None,
                "source_url": source_url,
                "chunk_text_sha256": chunk_sha,
                "source_locator": source_locator,
            },
        )
        for chunk_id in chunk_ids
    ]
    generated_answer = generator.generate(query, chunks)
    citation_items = [
        {
            "rank": index,
            "chunk_id": chunk_id,
            "citation_text": evidence_text,
            "citation_locator": {
                "page_id": page_ids[0] if page_ids else None,
                "section_id": section_ids[0] if section_ids else None,
                "section_path": section_path,
                "page_title": page_title,
                "source_url": source_url,
                "chunk_text_sha256": chunk_sha,
                "source_locator": source_locator,
            },
        }
        for index, chunk_id in enumerate(chunk_ids, start=1)
    ]
    source_artifact_id = repo_relative(text_review_pack)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "run_id": run_id,
        "generated_at": generated_at,
        "query_id": query_id,
        "safe_query_text": query,
        "query": query,
        "generated_answer": generated_answer,
        "answer_text": generated_answer,
        "cited_chunk_ids": chunk_ids,
        "retrieved_chunk_ids": chunk_ids,
        "citation_items": citation_items,
        "generation_provenance": {
            "generator_name": generator.name,
            "generator_class": "app.capabilities.rag.generation.ExtractiveGenerator",
            "answer_generation_execution": "source_bound_extractive_generator_no_llm",
            "generator_input_source": "text_namu_v2_review_pack.source_evidence_quote",
            "actual_generated_answer_output": True,
            "actual_llm_answer_generation_run": False,
            "live_llm_run": False,
            "local_llm_run": False,
            "external_cloud_llm_run": False,
            "deterministic_generation_run": True,
            "diagnostic_only": True,
            "official_metric_input": False,
            "generated_at": generated_at,
        },
        "retrieval_provenance": {
            "retrieval_run_id": None,
            "retrieval_run_current_slice": False,
            "retrieval_source": "source_bound_review_pack_locator",
            "source_artifact_id": source_artifact_id,
            "source_artifact_sha256": review_pack_sha,
            "production_index_used": False,
            "production_index_mutation": False,
            "retrieval_tuning_run": False,
        },
        "prompt_model_config_provenance": {
            "prompt_template_sha256": prompt_sha,
            "prompt_template_role": "diagnostic_source_bound_generation_contract",
            "model_name": "none_extractive_generator",
            "temperature": 0,
            "generator_name": generator.name,
            "max_context_chunks": len(chunks),
            "context_field": "source_evidence_quote",
        },
        "source_binding": {
            "source_artifact_id": source_artifact_id,
            "source_artifact_sha256": review_pack_sha,
            "source_locator": source_locator,
            "source_url": source_url,
            "chunk_text_sha256": chunk_sha,
        },
        "actual_generated_answer_output": True,
        "actual_llm_answer_generation_run": False,
        "live_llm_run": False,
        "local_llm_run": False,
        "external_cloud_llm_run": False,
        "diagnostic_only": True,
        "official_metric_input": False,
        "official_denominator_mutation": False,
        "promotion_evidence": False,
        "official_metric_computed": False,
    }


def source_row_blockers(row: Mapping[str, str]) -> list[str]:
    blockers: list[str] = []
    if not clean(row.get("query_id")):
        blockers.append("query_id_missing")
    if not clean(row.get("query")):
        blockers.append("safe_query_text_missing")
    if not clean(row.get("source_evidence_quote")):
        blockers.append("source_evidence_quote_missing")
    if not split_ids(row.get("expected_chunk_ids")):
        blockers.append("expected_chunk_ids_missing")
    if not clean(row.get("source_locator")):
        blockers.append("source_locator_missing")
    return blockers


def generated_answer_contract_errors(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not clean(row.get("query_id")):
        errors.append("query_id is required")
    if not clean(row.get("safe_query_text") or row.get("query")):
        errors.append("safe query text is required")
    if not clean(row.get("generated_answer") or row.get("answer") or row.get("final_answer")):
        errors.append("generated answer text is required")
    cited = clean_list(row.get("cited_chunk_ids"))
    retrieved = clean_list(row.get("retrieved_chunk_ids"))
    if not cited:
        errors.append("cited chunk ids are required")
    if not retrieved:
        errors.append("retrieved chunk ids are required")
    if cited and retrieved and not set(cited).issubset(set(retrieved)):
        errors.append("cited chunk ids must be present in retrieved chunk ids")
    citation_items = row.get("citation_items")
    if not isinstance(citation_items, list) or not citation_items:
        errors.append("citation text or locator is required for each cited chunk")
    else:
        item_by_chunk = {
            clean(item.get("chunk_id")): item for item in citation_items if isinstance(item, Mapping)
        }
        for chunk_id in cited:
            item = item_by_chunk.get(chunk_id)
            if not item:
                errors.append(f"{chunk_id}: citation item is missing")
                continue
            if not clean(item.get("citation_text")) and not item.get("citation_locator"):
                errors.append(f"{chunk_id}: citation text or locator is required")
    generation = row.get("generation_provenance")
    if not isinstance(generation, Mapping):
        errors.append("generation provenance is required")
    else:
        if not clean(generation.get("generator_name")):
            errors.append("generation provenance generator_name is required")
        if not clean(generation.get("answer_generation_execution")):
            errors.append("generation provenance answer_generation_execution is required")
        if generation.get("actual_generated_answer_output") is not True:
            errors.append("generation provenance actual_generated_answer_output must be true")
        if generation.get("official_metric_input") is not False:
            errors.append("generation provenance official_metric_input must be false")
    retrieval = row.get("retrieval_provenance")
    if not isinstance(retrieval, Mapping) or not (
        clean(retrieval.get("retrieval_run_id")) or clean(retrieval.get("source_artifact_id"))
    ):
        errors.append("retrieval run id or source artifact id is required")
    elif retrieval.get("production_index_used") is not False:
        errors.append("retrieval provenance production_index_used must be false")
    elif retrieval.get("production_index_mutation") is not False:
        errors.append("retrieval provenance production_index_mutation must be false")
    prompt = row.get("prompt_model_config_provenance")
    if not isinstance(prompt, Mapping):
        errors.append("prompt/model/config provenance is required")
    else:
        if not clean(prompt.get("prompt_template_sha256")):
            errors.append("prompt/model/config provenance prompt_template_sha256 is required")
        if not clean(prompt.get("model_name")):
            errors.append("prompt/model/config provenance model_name is required")
    if row.get("diagnostic_only") is not True:
        errors.append("diagnostic_only must be true")
    if row.get("official_metric_input") is not False:
        errors.append("official_metric_input must be explicit boolean false")
    if row.get("official_denominator_mutation") is not False:
        errors.append("official_denominator_mutation must be explicit boolean false")
    return errors


def contract_errors_by_query(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for index, row in enumerate(rows, start=1):
        row_errors = generated_answer_contract_errors(row)
        if row_errors:
            errors[clean(row.get("query_id")) or f"<row:{index}>"] = row_errors
    return errors


def build_report(
    *,
    run_id: str,
    generated_at: str,
    text_review_pack: Path,
    review_pack_sha: str | None,
    review_columns: list[str],
    normalization_report: Path,
    normalization: Mapping[str, Any],
    text: Mapping[str, Any],
    applied_decisions: Path | None,
    applied_text: Mapping[str, Any],
    candidate_ids: list[str],
    generated_rows: list[dict[str, Any]],
    missing_rows: list[dict[str, str]],
    contract_errors: dict[str, list[str]],
    output_jsonl: Path,
    output_report: Path,
    output_md: Path,
    prompt_sha: str,
) -> dict[str, Any]:
    policy_skipped = clean_list(text.get("policy_excluded_query_ids"))
    source_binding = clean_list(text.get("source_verification_required_query_ids"))
    diagnostic_default = clean_list(text.get("diagnostic_only_query_ids"))
    expected_revision = clean_list(text.get("expected_answer_or_evidence_revision_query_ids"))
    markers = text.get("review_marker_buckets") if isinstance(text.get("review_marker_buckets"), Mapping) else {}
    applied_carry_forward = clean_list(applied_text.get("query_ids"))
    unresolved = sorted(
        set(source_binding)
        | set(expected_revision)
        | set(clean_list(markers.get("needs_second_review")))
        | set(clean_list(markers.get("evidence_too_broad")))
        | set(clean_list(markers.get("ambiguous_query")))
        | set(applied_carry_forward)
    )
    official_metric_rows = [row for row in generated_rows if row.get("official_metric_input") is True]
    citation_complete = [
        row
        for row in generated_rows
        if row.get("cited_chunk_ids") and row.get("citation_items")
    ]
    provenance_complete = [
        row
        for row in generated_rows
        if isinstance(row.get("generation_provenance"), Mapping)
        and isinstance(row.get("retrieval_provenance"), Mapping)
        and isinstance(row.get("prompt_model_config_provenance"), Mapping)
    ]
    status = "PASS" if not missing_rows and not contract_errors else "FAIL"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": status,
        "phase": PHASE,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": len(official_metric_rows),
        "prior_generated_answer_output_found": False,
        "generated_or_collected": "generated_current_slice_source_bound_extractive",
        "artifact_paths": {
            "generated_answer_jsonl": repo_relative(output_jsonl),
            "generated_answer_jsonl_sha256": None,
            "report_json": repo_relative(output_report),
            "report_md": repo_relative(output_md),
        },
        "source_artifacts": {
            "text_review_pack": {
                "path": repo_relative(text_review_pack),
                "exists": text_review_pack.exists(),
                "sha256": review_pack_sha,
                "columns": review_columns,
            },
            "normalization_report": {
                "path": repo_relative(normalization_report),
                "exists": normalization_report.exists(),
                "sha256": sha256_if_exists(normalization_report),
                "schema_version": normalization.get("schema_version"),
            },
            "applied_decisions": {
                "path": repo_relative(applied_decisions) if applied_decisions is not None else None,
                "exists": applied_decisions.exists() if applied_decisions is not None else False,
                "sha256": sha256_if_exists(applied_decisions) if applied_decisions is not None else None,
            },
        },
        "candidate_review_rows": len(candidate_ids),
        "candidate_review_query_ids": candidate_ids,
        "generated_answer_rows": len(generated_rows),
        "generated_answer_query_ids": [row["query_id"] for row in generated_rows],
        "missing_generated_answer_rows": len(missing_rows),
        "missing_generated_answer_query_ids": [row["query_id"] for row in missing_rows],
        "missing_generated_answer_details": missing_rows,
        "rows_skipped_by_policy": len(policy_skipped),
        "rows_skipped_by_policy_query_ids": policy_skipped,
        "rows_skipped_by_unresolved_source_binding": len(unresolved),
        "rows_skipped_by_unresolved_source_binding_query_ids": unresolved,
        "rows_skipped_by_diagnostic_default": len(diagnostic_default),
        "rows_skipped_by_diagnostic_default_query_ids": diagnostic_default,
        "skip_subcounts": {
            "policy_excluded": len(policy_skipped),
            "source_binding_review_required": len(source_binding),
            "expected_answer_or_evidence_revision": len(expected_revision),
            "needs_second_review": len(clean_list(markers.get("needs_second_review"))),
            "evidence_too_broad": len(clean_list(markers.get("evidence_too_broad"))),
            "ambiguous_query": len(clean_list(markers.get("ambiguous_query"))),
            "applied_unresolved_carry_forward": len(applied_carry_forward),
            "diagnostic_only_default": len(diagnostic_default),
        },
        "citation_metadata_completeness": {
            "rows_with_cited_chunk_ids": sum(1 for row in generated_rows if row.get("cited_chunk_ids")),
            "rows_with_retrieved_chunk_ids": sum(1 for row in generated_rows if row.get("retrieved_chunk_ids")),
            "rows_with_citation_items": sum(1 for row in generated_rows if row.get("citation_items")),
            "complete_rows": len(citation_complete),
            "complete": len(citation_complete) == len(generated_rows),
        },
        "generated_answer_provenance_completeness": {
            "rows_with_generation_provenance": sum(
                1 for row in generated_rows if isinstance(row.get("generation_provenance"), Mapping)
            ),
            "rows_with_retrieval_provenance": sum(
                1 for row in generated_rows if isinstance(row.get("retrieval_provenance"), Mapping)
            ),
            "rows_with_prompt_model_config_provenance": sum(
                1 for row in generated_rows if isinstance(row.get("prompt_model_config_provenance"), Mapping)
            ),
            "complete_rows": len(provenance_complete),
            "complete": len(provenance_complete) == len(generated_rows),
        },
        "generation_config": {
            "generator_name": "extractive-v1",
            "model_name": "none_extractive_generator",
            "temperature": 0,
            "prompt_template_sha256": prompt_sha,
            "context_field": "source_evidence_quote",
            "expected_answer_text_used": False,
            "expected_evidence_label_invented": False,
            "citation_support_judgment_invented": False,
        },
        "validation": {
            "ok": status == "PASS",
            "contract_error_count": len(contract_errors),
            "contract_errors_by_query_id": contract_errors,
        },
        "guardrails": {
            "diagnostic_only": True,
            "official_metric_input_remains_false": len(official_metric_rows) == 0,
            "official_denominator_registry_changed": False,
            "official_denominator_opened": False,
            "production_namespace_mutation": False,
            "production_index_mutation": False,
            "production_vector_written": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "gold_registry_mutated": False,
            "route_fallback_labels_promoted": False,
            "policy_blocked_rows_counted_as_failures": False,
        },
        "remaining_blockers": [
            "Official TEXT answer/citation-support denominators remain closed.",
            "Citation-support official metric remains fail-closed until reviewed denominator policy opens it.",
            "Human answer/citation-support judgments are still required; this artifact contains generated answers and citation metadata only.",
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# TEXT/Namu Generated Answer Review Input",
        "",
        f"- status: `{report['status']}`",
        f"- diagnostic_only: `{report['diagnostic_only']}`",
        f"- generated answer rows: `{report['generated_answer_rows']}`",
        f"- missing generated answer rows: `{report['missing_generated_answer_rows']}`",
        f"- rows skipped by policy: `{report['rows_skipped_by_policy']}`",
        f"- rows skipped by unresolved/source-binding status: `{report['rows_skipped_by_unresolved_source_binding']}`",
        f"- official_metric_input_rows: `{report['official_metric_input_rows']}`",
        "",
        "## Completeness",
        "",
        f"- citation metadata complete: `{report['citation_metadata_completeness']['complete']}`",
        f"- provenance complete: `{report['generated_answer_provenance_completeness']['complete']}`",
        "",
        "## Guardrails",
        "",
        f"- official denominator opened: `{report['guardrails']['official_denominator_opened']}`",
        f"- production index mutation: `{report['guardrails']['production_index_mutation']}`",
        f"- candidate artifact mutated: `{report['guardrails']['candidate_artifact_mutated']}`",
    ]
    return "\n".join(lines) + "\n"


def read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def split_ids(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;,|]", text) if part.strip()]


def clean_list(value: object) -> list[str]:
    if isinstance(value, str):
        return split_ids(value)
    if not isinstance(value, Iterable):
        return []
    return [clean(item) for item in value if clean(item)]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
