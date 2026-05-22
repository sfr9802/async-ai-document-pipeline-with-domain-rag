"""Diagnostic-only PDF/XLSX local-LLM answer-quality benchmark.

The benchmark samples non-official, generation-allowed SourceAtom-backed
SearchView rows, creates harder user-like queries, and compares the current
legacy context shape against the locator-rich final context shape. Outputs stay
under ignored report directories and must not be treated as gold, qrels,
promotion evidence, or official denominator scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ROOT.parent
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.capabilities.rag.claude_generation import (  # noqa: E402
    _SYSTEM_PROMPT,
    _build_user_message,
)
from app.capabilities.rag.generation import RetrievedChunk  # noqa: E402


REPORT_DIR = AI_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_MANIFEST = (
    AI_ROOT
    / "eval"
    / "indexes"
    / "rag-data-all-source-citable-nonprod-v1"
    / "search_view_manifest.jsonl"
)
DEFAULT_SILVER_MANIFEST = (
    REPORT_DIR
    / "official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration_llm_natural_silver_manifest_all.jsonl"
)
DEFAULT_OUTPUT_DIR = REPORT_DIR / "quality"
DEFAULT_BASE_URL = "http://localhost:8081/v1"
DEFAULT_MODEL = "gemma4-e2b-local"
SCHEMA_VERSION = "rag_pdf_xlsx_llm_quality_benchmark_v1"
RUN_PREFIX = "pdf_xlsx_llm_quality"
FRIENDLY_SUFFIXES = ("주세요", "주세요.", "답하세요", "답하세요.", "무엇인가요?", "확인해 주세요.")
QUERY_REWRITE_MAX_ATTEMPTS = 2
QUERY_REWRITE_STYLE_CYCLE = (
    "fragment_no_verb: 2-6 words, no question mark, like a clipped search note",
    "messy_note: casual note with words like 이거/뭐였지/맞나 when natural",
    "terse_lookup: short direct lookup, may end with ?",
    "value_lookup: ask for the value/item only, compact and impatient",
    "ambiguous_answerable: incomplete but answerable note, no friendly ending",
    "correction_or_followup: sounds like a follow-up correction, not a full sentence",
)


@dataclass(frozen=True)
class EvidenceCase:
    case_id: str
    family: str
    source_atom_id: str
    doc_id: str
    section: str
    evidence_text: str
    locator: Mapping[str, Any]
    source_identity: str = ""
    locator_fingerprint: str = ""
    search_view_id: str = ""
    silver_query: str = ""
    silver_query_profile: str = ""
    silver_manifest_row_ordinal: int = 0
    silver_manifest_partition: str = ""
    weak_silver_candidate_id: str = ""
    source_candidate_id: str = ""
    join_key_used: str = ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_benchmark(
        manifest_path=Path(args.manifest),
        silver_manifest_path=Path(args.silver_manifest),
        output_dir=Path(args.output_dir),
        run_label=args.label,
        model=args.model,
        base_url=args.base_url,
        cases_per_family=args.cases_per_family,
        max_tokens=args.max_tokens,
        query_max_tokens=args.query_max_tokens,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] in {"PASS", "PASS_DRY_RUN"} else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--silver-manifest", default=str(DEFAULT_SILVER_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--cases-per-family", type=int, default=15)
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument("--query-max-tokens", type=int, default=160)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write prompts and query-quality metrics without calling the local LLM.",
    )
    return parser.parse_args(argv)


def run_benchmark(
    *,
    manifest_path: Path,
    silver_manifest_path: Path,
    output_dir: Path,
    run_label: str,
    model: str,
    base_url: str,
    cases_per_family: int,
    max_tokens: int,
    query_max_tokens: int,
    timeout_seconds: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    generated_at = utc_now()
    label = run_label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{RUN_PREFIX}_{label}_summary.json"
    rows_path = output_dir / f"{RUN_PREFIX}_{label}_responses.jsonl"

    silver_index = load_silver_seed_index(silver_manifest_path)
    cases = load_evidence_cases(
        manifest_path,
        cases_per_family=cases_per_family,
        silver_index=silver_index,
    )
    friendly_queries = [build_friendly_query(case) for case in cases]
    query_rows = []
    for index, case in enumerate(cases, start=1):
        if dry_run:
            seed = select_query_seed(case, ordinal=index)
            query_rows.append(
                {
                    **seed,
                    "query": build_challenge_query(case, ordinal=index),
                    "query_source": "dry_run_challenge_fallback",
                    "rewrite_parse_ok": False,
                    "rewrite_attempts": 0,
                    "query_rewrite_error": "",
                    "query_rewrite_raw_response": "",
                    "query_validation_failures": [],
                }
            )
            continue
        query_rows.append(
            rewrite_query_with_local_llm(
                case,
                ordinal=index,
                base_url=base_url,
                model=model,
                max_tokens=query_max_tokens,
                timeout_seconds=timeout_seconds,
            )
        )
    challenge_queries = [clean(row.get("query")) for row in query_rows]

    output_rows: list[dict[str, Any]] = []
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    with rows_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, (case, query, query_row) in enumerate(
            zip(cases, challenge_queries, query_rows),
            start=1,
        ):
            for prompt_mode in ("baseline_legacy_context", "final_locator_context"):
                system_prompt, user_prompt = build_prompt(case, query, prompt_mode=prompt_mode)
                started = time.perf_counter()
                if dry_run:
                    raw_response = ""
                    llm_error = ""
                    llm_elapsed_ms = 0.0
                else:
                    try:
                        raw_response = call_local_llm(
                            base_url=base_url,
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            max_tokens=max_tokens,
                            timeout_seconds=timeout_seconds,
                        )
                        llm_error = ""
                    except Exception as exc:  # pragma: no cover - exercised by live environment
                        raw_response = json.dumps(
                            {"local_llm_error": f"{type(exc).__name__}: {exc}"},
                            ensure_ascii=False,
                        )
                        llm_error = f"{type(exc).__name__}: {exc}"
                    llm_elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

                score = score_response(case, raw_response)
                row = {
                    "schema_version": f"{SCHEMA_VERSION}_row",
                    "run_label": label,
                    "generated_at": generated_at,
                    "row_index": index,
                    "case_id": case.case_id,
                    "family": case.family,
                    "source_atom_id": case.source_atom_id,
                    "search_view_id": case.search_view_id,
                    "locator_fingerprint": case.locator_fingerprint,
                    "source_identity_hash": sha256_text(case.source_identity) if case.source_identity else "",
                    "join_key_used": case.join_key_used,
                    "silver_manifest_partition": case.silver_manifest_partition,
                    "weak_silver_candidate_id": case.weak_silver_candidate_id,
                    "source_candidate_id": case.source_candidate_id,
                    "prompt_mode": prompt_mode,
                    "query": query,
                    "query_source": query_row.get("query_source"),
                    "query_style": classify_query_style(query),
                    "seed_query": query_row.get("seed_query"),
                    "seed_query_source": query_row.get("seed_query_source"),
                    "seed_query_profile": query_row.get("seed_query_profile"),
                    "query_rewrite_attempts": query_row.get("rewrite_attempts"),
                    "query_rewrite_parse_ok": query_row.get("rewrite_parse_ok"),
                    "query_rewrite_error": query_row.get("query_rewrite_error"),
                    "query_rewrite_raw_response": query_row.get("query_rewrite_raw_response"),
                    "rewritten_query_hash": sha256_text(query) if query else "",
                    "seed_query_hash": sha256_text(clean(query_row.get("seed_query"))),
                    "query_validation_failures": query_row.get("query_validation_failures"),
                    "query_validation_warnings": query_row.get("query_validation_warnings"),
                    "friendly_baseline_query": friendly_queries[index - 1],
                    "raw_response": raw_response,
                    "llm_elapsed_ms": llm_elapsed_ms,
                    "llm_error": llm_error,
                    "score": score,
                    "policy": policy_flags(),
                    "prompt_sha256": sha256_text(system_prompt + "\n" + user_prompt),
                }
                output_rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS_DRY_RUN" if dry_run else "PASS",
        "generated_at": generated_at,
        "run_label": label,
        "model": model,
        "base_url": base_url,
        "manifest": repo_relative(manifest_path),
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.exists() else "",
        "silver_manifest": repo_relative(silver_manifest_path),
        "silver_manifest_sha256": sha256_file(silver_manifest_path) if silver_manifest_path.exists() else "",
        "summary_path": repo_relative(summary_path),
        "responses_path": repo_relative(rows_path),
        "case_count": len(cases),
        "cases_by_family": dict(sorted(Counter(case.family for case in cases).items())),
        "silver_seed_match_count": sum(1 for case in cases if case.silver_query),
        "silver_join_summary": silver_join_summary(cases),
        "query_quality": {
            "friendly_baseline": query_quality_metrics(friendly_queries),
            "llm_rewrite_final": query_quality_metrics(challenge_queries),
        },
        "query_rewrite_summary": query_rewrite_summary(query_rows),
        "answer_quality": answer_quality_summary(output_rows),
        "failure_taxonomy": failure_taxonomy(output_rows),
        "sample_rows": sample_rows(output_rows, limit=30),
        "policy": policy_flags(),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def load_evidence_cases(
    manifest_path: Path,
    *,
    cases_per_family: int,
    silver_index: Mapping[str, Mapping[str, dict[str, Any]]] | None = None,
) -> list[EvidenceCase]:
    by_family: dict[str, list[EvidenceCase]] = {"PDF": [], "XLSX": []}
    for row in read_jsonl(manifest_path):
        family = clean(row.get("source_family") or row.get("sourceFamily")).upper()
        if family not in by_family:
            continue
        if official_denominator_overlap(row):
            continue
        if row_has_forbidden_policy_surface(row):
            continue
        if not bool(row.get("generation_source_allowed") or row.get("generationSourceAllowed")):
            continue
        if not bool(row.get("runtime_evidence_allowed") or row.get("runtimeEvidenceAllowed")):
            continue
        raw_evidence_text = clean(row.get("display_text") or row.get("bm25_text") or row.get("embedding_text"))
        embedding_text = clean(row.get("embedding_text"))
        locator = extract_locator(
            {**row, **parse_locator_text(embedding_text), **parse_locator_text(raw_evidence_text)}
        )
        evidence_text = safe_evidence_text(row, locator)
        if len(evidence_text) < 20:
            continue
        silver_seed = find_silver_seed(row, silver_index or {})
        case = EvidenceCase(
            case_id=f"{family.lower()}-{len(by_family[family]) + 1:03d}",
            family=family,
            source_atom_id=clean(row.get("source_atom_id") or row.get("sourceAtomId")),
            doc_id=clean(row.get("document_version_id") or row.get("document_id") or row.get("sourceIdentity")),
            section=case_section(family, locator, row),
            evidence_text=evidence_text,
            locator=locator,
            source_identity=canonical_source_identity(row),
            locator_fingerprint=clean(row.get("locator_fingerprint")),
            search_view_id=clean(row.get("search_view_id") or row.get("searchViewId")),
            silver_query=clean(silver_seed.get("generated_question_draft")),
            silver_query_profile=clean(silver_seed.get("query_quality_profile")),
            silver_manifest_row_ordinal=int(silver_seed.get("row_ordinal") or 0),
            silver_manifest_partition=clean(silver_seed.get("manifest_partition")),
            weak_silver_candidate_id=clean(silver_seed.get("weak_silver_candidate_id")),
            source_candidate_id=clean(silver_seed.get("source_candidate_id")),
            join_key_used=clean(silver_seed.get("_join_key_used")),
        )
        by_family[family].append(case)
    selected: list[EvidenceCase] = []
    for family in ("PDF", "XLSX"):
        candidates = sorted(
            by_family[family],
            key=lambda case: (
                0 if case.silver_query else 1,
                case.silver_manifest_row_ordinal or 999999,
                case.case_id,
            ),
        )
        selected.extend(candidates[:cases_per_family])
    return selected


def load_silver_seed_index(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {"pair": {}}
    if not path.exists():
        return index
    for row in read_jsonl(path):
        family = clean(row.get("source_family")).upper()
        if family not in {"PDF", "XLSX"}:
            continue
        if not silver_policy_safe(row):
            continue
        query = clean(row.get("generated_question_draft"))
        locator_fingerprint = clean(row.get("locator_fingerprint"))
        if not query or not locator_fingerprint:
            continue
        source_identity = clean(row.get("source_identity"))
        pair_key = silver_pair_key(family, locator_fingerprint, source_identity)
        indexed_row = dict(row)
        indexed_row["_join_key_used"] = "source_family+source_identity+locator_fingerprint"
        index["pair"].setdefault(pair_key, indexed_row)
    return index


def find_silver_seed(
    row: Mapping[str, Any],
    silver_index: Mapping[str, Mapping[str, dict[str, Any]]],
) -> dict[str, Any]:
    family = clean(row.get("source_family") or row.get("sourceFamily")).upper()
    locator_fingerprint = clean(row.get("locator_fingerprint"))
    source_identity = canonical_source_identity(row)
    pair = silver_index.get("pair", {})
    return pair.get(silver_pair_key(family, locator_fingerprint, source_identity)) or {}


def silver_pair_key(family: str, locator_fingerprint: str, source_identity: str) -> str:
    return f"{family}:{locator_fingerprint}:{source_identity}"


def silver_policy_safe(row: Mapping[str, Any]) -> bool:
    return (
        bool(row.get("diagnostic_only"))
        and bool(row.get("not_gold"))
        and bool(row.get("not_official_denominator"))
        and bool(row.get("not_official_qrels"))
        and not bool(row.get("official_metric_denominator_usage_allowed"))
        and not bool(row.get("promotion_evidence"))
        and not bool(row.get("threshold_tuning"))
        and not bool(row.get("winner_selection"))
    )


def canonical_source_identity(row: Mapping[str, Any]) -> str:
    family = clean(row.get("source_family") or row.get("sourceFamily")).upper()
    locator_fingerprint = clean(row.get("locator_fingerprint"))
    source_identity = clean(row.get("source_identity") or row.get("sourceIdentity"))
    if source_identity.startswith(f"{family}:") and locator_fingerprint and source_identity.endswith(
        f":{locator_fingerprint}"
    ):
        return source_identity
    doc_id = clean(row.get("document_version_id") or row.get("documentVersionId") or row.get("document_id"))
    search_unit_id = clean(row.get("search_unit_id") or row.get("parent_search_unit_id") or row.get("searchUnitId"))
    if family and doc_id and search_unit_id and locator_fingerprint:
        return f"{family}:{doc_id}:{search_unit_id}:{locator_fingerprint}"
    return source_identity


def official_denominator_overlap(row: Mapping[str, Any]) -> bool:
    return bool(row.get("official_denominator_overlap") or row.get("officialDenominatorOverlap"))


def row_has_forbidden_policy_surface(row: Mapping[str, Any]) -> bool:
    forbidden_keys = (
        "expected_answer",
        "expected_answer_source",
        "supporting_evidence",
        "supporting_evidence_source",
        "gold_or_label_source",
        "gold_label",
        "qrels_source",
        "qrel",
        "generated_silver_answer_source",
        "metric_result_source",
        "report_artifact_source",
    )
    if any(policy_value_present(row.get(key)) for key in forbidden_keys):
        return True
    return bool(row.get("quarantine") or row.get("review_only") or row.get("reviewOnly"))


def policy_value_present(value: object) -> bool:
    return value not in (None, "", [], {}, False)


def safe_evidence_text(row: Mapping[str, Any], locator: Mapping[str, Any]) -> str:
    if clean(row.get("source_family") or row.get("sourceFamily")).upper() == "XLSX":
        value = clean(locator.get("normalized_value"))
        if value:
            return strip_forbidden_prompt_text(value)
    raw = clean(row.get("display_text") or row.get("bm25_text") or row.get("embedding_text"))
    raw = strip_leading_locator_metadata(raw)
    return strip_forbidden_prompt_text(raw)


def strip_leading_locator_metadata(text: str) -> str:
    normalized = clean(text)
    if "Snapshot:" in normalized:
        return normalized.split("Snapshot:", 1)[-1].strip()
    if "normalized_value=" in normalized:
        return normalized.split("normalized_value=", 1)[-1].strip()
    return normalized


def strip_forbidden_prompt_text(text: str) -> str:
    sanitized = re.sub(r"\b[A-Za-z]:[\\/][^\s|]+", "[path]", clean(text))
    sanitized = re.sub(r"/(?:[^/\s|]+/){2,}[^/\s|]+", "[path]", sanitized)
    for token in (
        "expected_answer",
        "supporting_evidence",
        "gold_label",
        "gold_or_label_source",
        "qrels_source",
        "qrel",
    ):
        sanitized = re.sub(re.escape(token), "[policy-token]", sanitized, flags=re.I)
    return sanitized


def build_friendly_query(case: EvidenceCase) -> str:
    locator = short_locator_hint(case)
    if case.family == "XLSX":
        return f"제시된 XLSX 근거({locator})에서 확인되는 핵심 값 또는 항목을 한 문장으로 답하세요."
    return f"제시된 PDF 근거({locator})의 핵심 내용을 한 문장으로 답하세요."


def build_challenge_query(case: EvidenceCase, *, ordinal: int) -> str:
    keyword = source_keyword(case)
    locator = case.locator
    profile = ordinal % 6
    if case.family == "XLSX":
        sheet = clean(locator.get("sheet")) or "시트"
        cell_or_range = clean(locator.get("range")) or "해당 범위"
        target = clean(locator.get("target_column") or locator.get("column_label"))
        row = compact_row_label(clean(locator.get("row_label")))
        if profile == 1:
            return f"{sheet} {cell_or_range} 값"
        if profile == 2:
            return f"{row or keyword} {target or '값'}?"
        if profile == 3:
            return f"{sheet}에서 {keyword} 이거 맞나"
        if profile == 4:
            return f"{target or '값'}만, {cell_or_range}"
        if profile == 5:
            value_kind = "수치" if likely_numeric(clean(locator.get("normalized_value"))) else "항목"
            return f"{row or keyword or sheet} 근처 {value_kind} 확인"
        return f"{row or keyword or target or sheet} 나온 행이 어디였지"

    page = clean(locator.get("page"))
    region = human_region_label(clean(locator.get("region_type")))
    if profile == 1:
        return f"{keyword} {page or ''}쪽".strip()
    if profile == 2:
        return f"{keyword} 무슨 내용"
    if profile == 3:
        return f"{region}에 적힌 핵심만"
    if profile == 4:
        return f"{keyword} 확인"
    if profile == 5:
        return f"{page or '해당'}쪽 그 문구"
    return f"{keyword} 관련 내용만"


def select_query_seed(case: EvidenceCase, *, ordinal: int) -> dict[str, Any]:
    if case.silver_query:
        return {
            "seed_query": case.silver_query,
            "seed_query_source": "silver_seed",
            "seed_query_profile": case.silver_query_profile,
        }
    return {
        "seed_query": build_challenge_query(case, ordinal=ordinal),
        "seed_query_source": "challenge_seed",
        "seed_query_profile": "deterministic_non_gold_fallback",
    }


def rewrite_query_with_local_llm(
    case: EvidenceCase,
    *,
    ordinal: int,
    base_url: str,
    model: str,
    max_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    def client(system_prompt: str, user_prompt: str) -> str:
        return call_local_llm(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            temperature=0.7,
        )

    return rewrite_query_with_client(case, ordinal=ordinal, llm_client=client)


def rewrite_query_with_client(
    case: EvidenceCase,
    *,
    ordinal: int,
    llm_client: Any,
    seed_query: str | None = None,
) -> dict[str, Any]:
    seed = select_query_seed(case, ordinal=ordinal)
    if seed_query is not None:
        seed = {
            **seed,
            "seed_query": clean(seed_query),
            "seed_query_source": "silver_seed" if clean(seed_query) == case.silver_query else "provided_seed",
        }

    raw_response = ""
    parse_ok = False
    validation_failures: list[str] = []
    validation_warnings: list[str] = []
    error = ""
    query = ""
    for attempt in range(1, QUERY_REWRITE_MAX_ATTEMPTS + 1):
        system_prompt, user_prompt = build_query_rewrite_prompt(
            case,
            seed_query=clean(seed.get("seed_query")),
            ordinal=ordinal,
            retry_failures=validation_failures if attempt > 1 else [],
        )
        try:
            raw_response = llm_client(system_prompt, user_prompt)
            parsed, parse_ok = parse_json_response(raw_response)
            query = sanitize_rewritten_query(clean(parsed.get("query")))
            validation_failures = validate_rewritten_query(
                query,
                case=case,
                seed_query=clean(seed.get("seed_query")),
            )
            validation_warnings = query_validation_warnings(query, case=case)
        except Exception as exc:  # pragma: no cover - exercised by live environment
            error = f"{type(exc).__name__}: {exc}"
            validation_failures = ["rewrite_llm_error"]
            validation_warnings = []
            parse_ok = False
            query = ""
        if query and parse_ok and not validation_failures:
            return {
                **seed,
                "query": query,
                "query_source": "llm_rewrite",
                "query_style": classify_query_style(query),
                "query_rewrite_raw_response": raw_response,
                "query_rewrite_error": error,
                "rewrite_parse_ok": parse_ok,
                "rewrite_attempts": attempt,
                "query_validation_failures": [],
                "query_validation_warnings": validation_warnings,
            }

    fallback = build_challenge_query(case, ordinal=ordinal)
    return {
        **seed,
        "query": fallback,
        "query_source": "challenge_fallback_after_llm_rewrite",
        "query_style": classify_query_style(fallback),
        "query_rewrite_raw_response": raw_response,
        "query_rewrite_error": error,
        "rewrite_parse_ok": parse_ok,
        "rewrite_attempts": QUERY_REWRITE_MAX_ATTEMPTS,
        "query_validation_failures": validation_failures,
        "query_validation_warnings": validation_warnings,
    }


def build_query_rewrite_prompt(
    case: EvidenceCase,
    *,
    seed_query: str,
    ordinal: int,
    retry_failures: list[str] | None = None,
) -> tuple[str, str]:
    system_prompt = (
        "You rewrite Korean diagnostic RAG benchmark queries. Use the given "
        "weak-silver seed, safe locator hints, and source excerpt only as "
        "non-gold inspiration. Produce one realistic user query that remains "
        "answerable from the source excerpt but sounds less uniform and less "
        "polite than template QA. Return JSON only with keys `query`, `style`, "
        "and `rationale`."
    )
    style_hint = (
        "Vary style across rows: terse lookup, fragment, messy note, value lookup, "
        "ambiguous-but-answerable, or short correction. Prefer Korean. Avoid "
        "friendly endings like 주세요/답하세요, full file names, file extensions, "
        "absolute paths, source ids, locator fingerprints, bbox text, qrels, gold, "
        "or expected-answer language. Do not copy the seed verbatim."
    )
    retry = ""
    if retry_failures:
        retry = "\nPrevious rewrite failed validation: " + ", ".join(retry_failures)
    user_prompt = "\n".join(
        [
            f"Row ordinal: {ordinal}",
            f"Family: {case.family}",
            f"Weak-silver seed query (diagnostic only, not gold): {seed_query}",
            f"Silver query profile: {case.silver_query_profile or 'none'}",
            f"Target style for this row: {query_rewrite_style(ordinal)}",
            f"Safe locator hints: {safe_query_locator_hints(case)}",
            f"Required exact source terms: {', '.join(source_terms_for_query(case))}",
            f"Source excerpt: {shorten(case.evidence_text, 700)}",
            style_hint,
            "Hard constraint: include at least one required exact source term in the query.",
            retry,
            'Return shape: {"query":"...","style":"...","rationale":"..."}',
        ]
    )
    return system_prompt, user_prompt


def sanitize_rewritten_query(query: str) -> str:
    text = clean(query).strip("\"'` ")
    text = re.sub(r"^(질문|query)\s*[:：]\s*", "", text, flags=re.I)
    return shorten(text, 120)


def query_rewrite_style(ordinal: int) -> str:
    return QUERY_REWRITE_STYLE_CYCLE[(ordinal - 1) % len(QUERY_REWRITE_STYLE_CYCLE)]


def validate_rewritten_query(query: str, *, case: EvidenceCase, seed_query: str) -> list[str]:
    failures: list[str] = []
    if len(query) < 3:
        failures.append("query_too_short")
    if len(query) > 120:
        failures.append("query_too_long")
    if clean(query) == clean(seed_query):
        failures.append("query_copied_seed")
    if is_friendly_query(query):
        failures.append("friendly_template_ending")
    if contains_internal_query_surface(query):
        failures.append("internal_surface_leak")
    return failures


def query_validation_warnings(query: str, *, case: EvidenceCase) -> list[str]:
    if not source_term_overlap(query, case) and not locator_query_overlap(query, case.locator):
        return ["low_source_overlap"]
    return []


def source_term_overlap(query: str, case: EvidenceCase) -> bool:
    query_tokens = set(meaningful_tokens_ordered(query))
    for term in source_terms_for_query(case):
        if term in query_tokens:
            return True
        if any(term in token or token in term for token in query_tokens if len(token) >= 2):
            return True
    return False


def contains_internal_query_surface(query: str) -> bool:
    lower = clean(query).lower()
    blocked = (
        ".pdf",
        ".xlsx",
        "sourceatom",
        "source_atom",
        "srcatom",
        "searchview",
        "docv_",
        "local-storage",
        "locator_fingerprint",
        "source_identity",
        "source_pdf_path",
        "bbox",
        "d:/",
        "c:/",
    )
    return any(token in lower for token in blocked)


def locator_query_overlap(query: str, locator: Mapping[str, Any]) -> bool:
    text = clean(query)
    for key in ("sheet", "cell", "row_label", "target_column", "column_label", "page"):
        value = human_query_term(clean(locator.get(key)))
        if value and value in text:
            return True
    return False


def query_quality_metrics(queries: Iterable[str]) -> dict[str, Any]:
    query_list = [clean(query) for query in queries if clean(query)]
    prefix_counts = Counter(query[:6] for query in query_list)
    styles = Counter(classify_query_style(query) for query in query_list)
    friendly_count = sum(1 for query in query_list if is_friendly_query(query))
    avg_chars = (
        round(sum(len(query) for query in query_list) / len(query_list), 3)
        if query_list
        else 0.0
    )
    return {
        "query_count": len(query_list),
        "query_style_counts": dict(sorted(styles.items())),
        "query_style_count": len(styles),
        "friendly_suffix_count": friendly_count,
        "friendly_suffix_ratio": round(friendly_count / len(query_list), 4) if query_list else 0.0,
        "max_same_six_char_prefix_count": max(prefix_counts.values(), default=0),
        "avg_chars": avg_chars,
        "short_fragment_count": sum(1 for query in query_list if len(query.split()) <= 3),
        "question_mark_ratio": (
            round(sum("?" in query or "？" in query for query in query_list) / len(query_list), 4)
            if query_list
            else 0.0
        ),
    }


def classify_query_style(query: str) -> str:
    text = clean(query)
    if any(token in text for token in ("이거", "맞나", "어디였지", "그 문구", "뭐야", "뭐죠", "뭐임", "어떻게 돼")):
        return "messy_user_like"
    if any(token in text for token in ("값만", "핵심만", "내용만", "만,")):
        return "direct_value_or_summary"
    if any(token in text for token in ("쪽", "시트", "범위", "셀")):
        return "locator_hint"
    if "무슨 내용" in text:
        return "content_probe"
    if len(text.split()) <= 3:
        return "short_fragment"
    if text.endswith("?") or text.endswith("？"):
        return "terse_question"
    return "source_grounded"


def build_prompt(
    case: EvidenceCase,
    query: str,
    *,
    prompt_mode: str,
) -> tuple[str, str]:
    system = (
        _SYSTEM_PROMPT
        + "\n\nDiagnostic benchmark response contract: return only valid JSON with keys "
        "`answer`, `citations`, and `abstain_reason`. `citations` must be a list of "
        "objects with `citation_id` and `locator`. Keep `answer` to one short "
        "sentence. If `answer` is non-empty, `abstain_reason` must be an empty "
        "string. Use compact locators such as `page=1; bbox=[...]` or "
        "`sheet=Sheet1; cell=A1`; do not copy full absolute paths into the JSON."
    )
    chunk = case_to_chunk(case)
    if prompt_mode == "final_locator_context":
        user = _build_user_message(query, [chunk])
    elif prompt_mode == "baseline_legacy_context":
        user = build_legacy_user_message(query, [chunk])
    else:
        raise ValueError(f"unknown prompt_mode: {prompt_mode}")
    user += (
        "\n\nReturn JSON only. Example shape: "
        '{"answer":"...","citations":[{"citation_id":"S1","locator":"..."}],'
        '"abstain_reason":""}'
    )
    return system, user


def build_legacy_user_message(query: str, chunks: list[RetrievedChunk]) -> str:
    lines = [f"질문: {query}", "", "관련 자료:"]
    for index, chunk in enumerate(chunks, start=1):
        del index
        lines.append(f"[1] {chunk.doc_id}#{chunk.section} (score={chunk.score:.3f})")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines)


def score_response(case: EvidenceCase, raw_response: str) -> dict[str, Any]:
    parsed, parse_ok = parse_json_response(raw_response)
    answer = clean(parsed.get("answer")) if parse_ok else clean(raw_response)
    citations = parsed.get("citations") if parse_ok else []
    citation_valid = citation_id_present(citations, raw_response, "S1")
    locator_text = citation_locator_text(citations)
    expected_value = clean(case.locator.get("normalized_value"))
    value_supported = normalized_value_supported(expected_value, answer)
    text_supported = evidence_token_overlap(answer, case.evidence_text) >= 2
    locator_only = is_locator_only_answer(case, answer)
    answer_present = bool(answer) and not clean(parsed.get("abstain_reason"))

    failure_types: list[str] = []
    if not parse_ok:
        failure_types.append("invalid_json")
    if not answer_present:
        failure_types.append("missing_answer")
    if locator_only:
        failure_types.append("locator_only_answer")
    if expected_value and not value_supported:
        failure_types.append("missing_expected_value")
    if not expected_value and not text_supported:
        failure_types.append("low_evidence_overlap")
    if not citation_valid:
        failure_types.append("citation_missing_or_invalid")
    if case.family == "PDF" and not pdf_locator_valid(locator_text, case.locator):
        failure_types.append("pdf_locator_missing")
    if case.family == "XLSX" and not xlsx_locator_valid(locator_text, case.locator):
        failure_types.append("xlsx_locator_missing")

    return {
        "parse_ok": parse_ok,
        "answer_present": answer_present,
        "citation_valid": citation_valid,
        "value_supported": value_supported,
        "text_supported": text_supported,
        "locator_only_answer": locator_only,
        "failure_types": failure_types,
        "quality_pass": not failure_types,
    }


def answer_quality_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = f"{row.get('prompt_mode')}::{row.get('family')}"
        grouped.setdefault(key, []).append(row)
        grouped.setdefault(str(row.get("prompt_mode")), []).append(row)
    summary: dict[str, Any] = {}
    for key, items in sorted(grouped.items()):
        scores = [as_mapping(item.get("score")) for item in items]
        total = len(scores)
        summary[key] = {
            "rows": total,
            "quality_pass": sum(bool(score.get("quality_pass")) for score in scores),
            "parse_ok": sum(bool(score.get("parse_ok")) for score in scores),
            "citation_valid": sum(bool(score.get("citation_valid")) for score in scores),
            "value_supported": sum(bool(score.get("value_supported")) for score in scores),
            "text_supported": sum(bool(score.get("text_supported")) for score in scores),
            "quality_pass_rate": (
                round(sum(bool(score.get("quality_pass")) for score in scores) / total, 4)
                if total
                else 0.0
            ),
        }
    baseline = summary.get("baseline_legacy_context", {})
    final = summary.get("final_locator_context", {})
    delta_by_family = {}
    for family in ("PDF", "XLSX"):
        family_baseline = summary.get(f"baseline_legacy_context::{family}", {})
        family_final = summary.get(f"final_locator_context::{family}", {})
        delta_by_family[family] = {
            "quality_pass": int(family_final.get("quality_pass") or 0)
            - int(family_baseline.get("quality_pass") or 0),
            "quality_pass_rate": round(
                float(family_final.get("quality_pass_rate") or 0.0)
                - float(family_baseline.get("quality_pass_rate") or 0.0),
                4,
            ),
            "citation_valid": int(family_final.get("citation_valid") or 0)
            - int(family_baseline.get("citation_valid") or 0),
        }
    summary["delta_by_family_final_minus_baseline"] = delta_by_family
    summary["delta_final_minus_baseline"] = {
        "diagnostic_aggregate_only": True,
        "quality_pass": int(final.get("quality_pass") or 0) - int(baseline.get("quality_pass") or 0),
        "quality_pass_rate": round(
            float(final.get("quality_pass_rate") or 0.0)
            - float(baseline.get("quality_pass_rate") or 0.0),
            4,
        ),
        "citation_valid": int(final.get("citation_valid") or 0) - int(baseline.get("citation_valid") or 0),
    }
    return summary


def failure_taxonomy(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, Counter[str]] = {}
    for row in rows:
        mode = clean(row.get("prompt_mode"))
        by_mode.setdefault(mode, Counter())
        for failure in as_mapping(row.get("score")).get("failure_types") or []:
            by_mode[mode][clean(failure)] += 1
    return {mode: dict(sorted(counter.items())) for mode, counter in sorted(by_mode.items())}


def query_rewrite_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    sources = Counter(clean(row.get("query_source")) for row in rows)
    seed_sources = Counter(clean(row.get("seed_query_source")) for row in rows)
    failures: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    for row in rows:
        for failure in row.get("query_validation_failures") or []:
            failures[clean(failure)] += 1
        for warning in row.get("query_validation_warnings") or []:
            warnings[clean(warning)] += 1
    return {
        "rows": len(rows),
        "query_source_counts": dict(sorted(sources.items())),
        "seed_query_source_counts": dict(sorted(seed_sources.items())),
        "silver_seed_rows": sum(clean(row.get("seed_query_source")) == "silver_seed" for row in rows),
        "llm_rewrite_rows": sum(clean(row.get("query_source")) == "llm_rewrite" for row in rows),
        "fallback_rows": sum("fallback" in clean(row.get("query_source")) for row in rows),
        "rewrite_parse_ok_rows": sum(bool(row.get("rewrite_parse_ok")) for row in rows),
        "validation_failure_counts": dict(sorted(failures.items())),
        "validation_warning_counts": dict(sorted(warnings.items())),
    }


def silver_join_summary(cases: list[EvidenceCase]) -> dict[str, Any]:
    by_family: dict[str, dict[str, int]] = {}
    partitions = Counter(case.silver_manifest_partition or "none" for case in cases)
    for case in cases:
        entry = by_family.setdefault(case.family, {"cases": 0, "silver_seed_matches": 0})
        entry["cases"] += 1
        if case.silver_query:
            entry["silver_seed_matches"] += 1
    return {
        "cases": len(cases),
        "silver_seed_matches": sum(1 for case in cases if case.silver_query),
        "join_key": "source_family+source_identity+locator_fingerprint",
        "locator_only_fallback_enabled": False,
        "by_family": dict(sorted(by_family.items())),
        "manifest_partition_counts": dict(sorted(partitions.items())),
    }


def sample_rows(rows: list[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((clean(row.get("family")), clean(row.get("prompt_mode"))), []).append(row)
    ordered_rows: list[Mapping[str, Any]] = []
    keys = [
        ("PDF", "baseline_legacy_context"),
        ("PDF", "final_locator_context"),
        ("XLSX", "baseline_legacy_context"),
        ("XLSX", "final_locator_context"),
    ]
    for offset in range(max((len(items) for items in grouped.values()), default=0)):
        for key in keys:
            items = grouped.get(key, [])
            if offset < len(items):
                ordered_rows.append(items[offset])
            if len(ordered_rows) >= limit:
                break
        if len(ordered_rows) >= limit:
            break

    samples = []
    for row in ordered_rows[:limit]:
        samples.append(
            {
                "case_id": row.get("case_id"),
                "family": row.get("family"),
                "prompt_mode": row.get("prompt_mode"),
                "query": row.get("query"),
                "query_source": row.get("query_source"),
                "seed_query": row.get("seed_query"),
                "raw_response": row.get("raw_response"),
                "score": row.get("score"),
            }
        )
    return samples


def case_to_chunk(case: EvidenceCase) -> RetrievedChunk:
    metadata = {
        "source_atom_hydrated_from_registry": True,
        "source_family": case.family,
        "source_atom_id": case.source_atom_id,
        "document_version_id": case.doc_id,
        **dict(case.locator),
    }
    return RetrievedChunk(
        chunk_id=case.source_atom_id or case.case_id,
        doc_id=case.doc_id,
        section=case.section,
        text=case.evidence_text,
        score=0.9,
        search_unit_id=clean(case.locator.get("search_unit_id")),
        metadata_json=metadata,
    )


def call_local_llm(
    *,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout_seconds: int,
    temperature: float = 0.0,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    choices = body.get("choices") if isinstance(body, Mapping) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else {}
        if isinstance(message, Mapping):
            return clean(message.get("content"))
    return json.dumps(body, ensure_ascii=False)


def parse_json_response(raw_response: str) -> tuple[dict[str, Any], bool]:
    text = clean(raw_response)
    if not text:
        return {}, False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}, False
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}, False
    if not isinstance(parsed, Mapping):
        return {}, False
    return dict(parsed), True


def citation_id_present(citations: object, raw_response: str, citation_id: str) -> bool:
    wanted = citation_id.strip("[]")
    if isinstance(citations, list):
        for citation in citations:
            if not isinstance(citation, Mapping):
                continue
            value = clean(citation.get("citation_id") or citation.get("id"))
            if value.strip("[]") == wanted:
                return True
    return f"[{wanted}]" in raw_response or wanted in clean(raw_response)


def citation_locator_text(citations: object) -> str:
    if not isinstance(citations, list):
        return ""
    parts = []
    for citation in citations:
        if isinstance(citation, Mapping):
            parts.append(clean(citation.get("locator") or citation.get("source_locator")))
    return " ".join(parts)


def is_locator_only_answer(case: EvidenceCase, answer: str) -> bool:
    normalized = clean(answer)
    if not normalized:
        return False
    expected_value = clean(case.locator.get("normalized_value"))
    if expected_value and expected_value in normalized:
        return False
    locator_values = [
        clean(case.locator.get(key))
        for key in ("sheet", "cell", "range", "page", "source_pdf_path", "workbook")
    ]
    locator_values = [value for value in locator_values if value]
    return any(value in normalized for value in locator_values) and evidence_token_overlap(normalized, case.evidence_text) < 2


def locator_mentions(locator_text: str, locator: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    text = clean(locator_text)
    if not text:
        return False
    for key in keys:
        value = clean(locator.get(key))
        if value and value in text:
            return True
    return False


def pdf_locator_valid(locator_text: str, locator: Mapping[str, Any]) -> bool:
    if clean(locator.get("bbox")):
        return "bbox" in clean(locator_text).lower() or locator_mentions(locator_text, locator, ("bbox",))
    return locator_mentions(locator_text, locator, ("page", "source_pdf_path"))


def xlsx_locator_valid(locator_text: str, locator: Mapping[str, Any]) -> bool:
    if clean(locator.get("cell")) or clean(locator.get("range")):
        return locator_mentions(locator_text, locator, ("cell", "range"))
    return locator_mentions(locator_text, locator, ("sheet", "workbook"))


def evidence_token_overlap(answer: str, evidence_text: str) -> int:
    answer_tokens = meaningful_tokens(answer)
    evidence_tokens = meaningful_tokens(evidence_text)
    return len(answer_tokens & evidence_tokens)


def normalized_value_supported(expected_value: str, answer: str) -> bool:
    expected = clean(expected_value)
    normalized_answer = clean(answer)
    if not expected:
        return False
    if expected in normalized_answer:
        return True
    if likely_numeric(expected):
        return digits_only(expected) == digits_only(normalized_answer) or digits_only(expected) in digits_only(
            normalized_answer
        )
    expected_tokens = set(meaningful_tokens_ordered(expected))
    answer_tokens = set(meaningful_tokens_ordered(normalized_answer))
    overlap = expected_tokens & answer_tokens
    if len(overlap) >= 2:
        return True
    return any(len(token) >= 5 and any(token in answer_token for answer_token in answer_tokens) for token in expected_tokens)


def digits_only(value: str) -> str:
    return "".join(re.findall(r"\d+", clean(value)))


def meaningful_tokens(value: str) -> set[str]:
    return set(meaningful_tokens_ordered(value))


def source_terms_for_query(case: EvidenceCase) -> list[str]:
    terms: list[str] = []
    for value in (
        case.evidence_text,
        compact_spaced_hangul(case.evidence_text),
        clean(case.locator.get("row_label")),
        clean(case.locator.get("target_column") or case.locator.get("column_label")),
    ):
        for token in meaningful_tokens_ordered(value):
            if usable_query_token(token) and token not in terms:
                terms.append(token)
            if len(terms) >= 10:
                return terms
    return terms or [source_keyword(case)]


def compact_spaced_hangul(value: str) -> str:
    return re.sub(r"(?<=[가-힣])\s+(?=[가-힣])", "", clean(value))


def meaningful_tokens_ordered(value: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣一-龥ぁ-ゟァ-ヿ]+", clean(value))
    return [token for token in tokens if len(token) >= 2]


def extract_locator(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "source_pdf_path",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "column_label",
        "target_column",
        "normalized_value",
        "source_path",
        "search_unit_id",
    )
    locator = {key: row.get(key) for key in keys if row.get(key) not in (None, "", [], {})}
    if "search_unit_id" not in locator:
        search_unit = clean(row.get("parent_search_unit_id") or row.get("searchUnitId"))
        if search_unit:
            locator["search_unit_id"] = search_unit
    return locator


def parse_locator_text(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key in (
        "source_pdf_path",
        "source_path",
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "column_label",
        "target_column",
        "normalized_value",
        "page",
        "physical_page_index",
        "region_type",
    ):
        match = re.search(rf"{re.escape(key)}=([^\n|]+)", text)
        if match:
            parsed[key] = clean_locator_value(match.group(1))
    bbox_match = re.search(r"bbox=(\[[^\]]+\])", text)
    if bbox_match:
        try:
            parsed["bbox"] = json.loads(bbox_match.group(1))
        except json.JSONDecodeError:
            parsed["bbox"] = bbox_match.group(1)
    return parsed


def case_section(family: str, locator: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    if family == "XLSX":
        return clean(locator.get("sheet") or locator.get("range") or row.get("search_view_id") or "xlsx")
    if family == "PDF":
        page = clean(locator.get("page"))
        return f"page-{page}" if page else "pdf"
    return clean(row.get("search_view_id") or "source")


def source_keyword(case: EvidenceCase) -> str:
    if case.family == "XLSX":
        for key in ("target_column", "row_label", "normalized_value", "cell", "range"):
            value = clean(case.locator.get(key))
            if value:
                return shorten(human_query_term(value), 24)
    for token in meaningful_tokens_ordered(case.evidence_text):
        if usable_query_token(token):
            return shorten(token, 24)
    return "해당 내용"


def short_locator_hint(case: EvidenceCase) -> str:
    locator = case.locator
    if case.family == "XLSX":
        parts = [
            clean(locator.get("workbook")),
            clean(locator.get("sheet")),
            clean(locator.get("cell") or locator.get("range")),
        ]
    else:
        parts = [
            clean(locator.get("source_pdf_path")),
            f"page={clean(locator.get('page'))}" if clean(locator.get("page")) else "",
        ]
    return ", ".join(part for part in parts if part) or f"{case.family} locator"


def safe_query_locator_hints(case: EvidenceCase) -> str:
    locator = case.locator
    if case.family == "XLSX":
        parts = [
            f"sheet={clean(locator.get('sheet'))}" if clean(locator.get("sheet")) else "",
            f"cell={clean(locator.get('cell'))}" if clean(locator.get("cell")) else "",
            f"row={compact_row_label(clean(locator.get('row_label')))}" if clean(locator.get("row_label")) else "",
            f"target={clean(locator.get('target_column') or locator.get('column_label'))}"
            if clean(locator.get("target_column") or locator.get("column_label"))
            else "",
        ]
    else:
        parts = [
            f"page={clean(locator.get('page'))}" if clean(locator.get("page")) else "",
            f"region={human_region_label(clean(locator.get('region_type')))}" if clean(locator.get("region_type")) else "",
        ]
    return " | ".join(part for part in parts if part) or case.family


def compact_row_label(value: str) -> str:
    if not value:
        return ""
    parts = [part.strip() for part in value.split("|") if part.strip()]
    return " ".join(parts[:2]) if parts else shorten(value, 30)


def usable_query_token(token: str) -> bool:
    lower = token.lower()
    if len(token) < 3:
        return False
    blocked = {
        "sourceatom",
        "family",
        "identity",
        "locator",
        "snapshot",
        "source",
        "path",
        "source_pdf_path",
        "source_path",
        "text_block",
        "paragraph",
        "page",
        "pdf",
        "xlsx",
        "workbook",
        "sheet",
        "range",
        "cell",
        "normalized_value",
    }
    if lower in blocked:
        return False
    if lower.startswith(("docv_", "srcatom_", "searchview_", "local", "storage")):
        return False
    if token.isdigit() and len(token) > 8:
        return False
    if re.fullmatch(r"[IVXLCDM]+", token):
        return False
    return bool(re.search(r"[가-힣A-Za-z一-龥ぁ-ゟァ-ヿ]", token))


def human_query_term(value: str) -> str:
    text = clean(value)
    for marker in (" snapshot=", " value=", " source_path=", " workbook="):
        if marker in text:
            text = text.split(marker, 1)[0]
    if "|" in text:
        parts = [part.strip() for part in text.split("|") if part.strip()]
        text = " ".join(parts[:2])
    if "=" in text:
        text = text.split("=", 1)[-1].strip()
    return text or value


def clean_locator_value(value: str) -> str:
    text = clean(value)
    for marker in (" Snapshot:", " snapshot=", " value=", " SourceAtom:", " Locator:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def workbook_stem(value: str) -> str:
    if not value:
        return "엑셀"
    return shorten(Path(value).stem, 26)


def pdf_stem(value: str) -> str:
    if not value:
        return "보고서"
    stem = Path(value).stem
    if "_" in stem and re.search(r"\d{5,}", stem):
        return "보고서"
    return shorten(stem, 22)


def human_region_label(value: str) -> str:
    labels = {
        "text_block": "본문",
        "paragraph": "문단",
        "paragraph_window": "문단",
        "table_body": "표",
    }
    return labels.get(value, value or "영역")


def likely_numeric(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    digit_count = sum(char.isdigit() for char in text)
    return digit_count >= 3 and digit_count >= max(1, len(text) // 2)


def is_friendly_query(query: str) -> bool:
    return clean(query).endswith(FRIENDLY_SUFFIXES)


def shorten(value: str, max_chars: int) -> str:
    text = clean(value)
    return text if len(text) <= max_chars else text[:max_chars].rstrip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def policy_flags() -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "synthetic_or_non_gold_queries_only": True,
        "not_gold": True,
        "not_official_denominator": True,
        "not_official_qrels": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_or_label_mutation": False,
        "expected_answer_or_supporting_evidence_used": False,
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
