"""XLSX pre-silver risk-closure guards.

This module is intentionally XLSX-only.  It does not generate silver data,
does not tune retrieval, and does not create an answer-generation official
denominator.  The helpers here give official wrappers and preflight reports a
single fail-closed place for route, artifact, and strict-status checks.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER = Path(__file__).resolve().parents[1]
ROOT = AI_WORKER.parent

STRICT_APPROVAL_STATUS = "APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT"
BLOCKED_STATUS = "BLOCKED_PENDING_PRE_SILVER_RISK_FIXES"

CURRENT_XLSX_DENOMINATOR_KEY = "track_a_xlsx_human_review_normalized_v0"
LEGACY_XLSX_V3_DENOMINATOR_KEY = "track_a_xlsx_reviewed_positive"
OFFICIAL_REGISTRY = ROOT / "ai" / "eval" / "eval_queries" / "official_denominator_registry.json"

XLSX_CANDIDATE_NAMESPACE = "rag-ingestion-v2-xlsx-candidate-v1"
XLSX_CANDIDATE_INDEX_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
CURRENT_XLSX_RETRIEVAL_GOLD = Path(
    "eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
)
CANONICAL_XLSX_RETRIEVAL_GOLD_PATH = (AI_WORKER / CURRENT_XLSX_RETRIEVAL_GOLD).resolve()
CANONICAL_XLSX_CANDIDATE_INDEX_DIR = (AI_WORKER / XLSX_CANDIDATE_INDEX_DIR).resolve()
CURRENT_NORMALIZED_REPO_PATH = "ai/eval/eval_queries/gold_queries_xlsx_human_review_normalized_v0.csv"
CURRENT_OFFICIAL_REPO_PATH = "ai/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0.csv"
CURRENT_RETRIEVAL_REPO_PATH = (
    "ai/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
)
CURRENT_NORMALIZATION_REPORT_REPO_PATH = (
    "reports/rag_eval/rag-ingestion/rag_xlsx_human_review_gold_normalization_report.json"
)

EXPECTED_NORMALIZED_ROW_COUNT = 50
EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT = 23
EXPECTED_XLSX_ANSWER_DENOMINATOR = 0
SPECIAL_NON_OFFICIAL_QUERY_IDS = {
    "gq_xlsx_date_number_format_003",
    "gq_xlsx_aggregation_001",
}

FORBIDDEN_AGENTIC_RETRIEVER_MARKERS = (
    "global",
    "library_search",
    "text",
    "namu",
    "pdf",
)

REQUIRED_AGENTIC_ITERATION_FIELDS = (
    "trace_id",
    "query_id",
    "eval_mode",
    "track",
    "namespace",
    "iteration",
    "action_type",
    "retriever_or_tool_name",
    "input_query",
    "candidate_ids",
    "selected_context_ids",
    "stop_reason",
)


class XlsxPreSilverRiskError(RuntimeError):
    """Raised when an XLSX pre-silver invariant is violated."""


def validate_official_xlsx_eval_route(
    *,
    eval_mode: str,
    track: str,
    agent_orchestrator_enabled: bool,
    retrieval_backend: str,
    namespace: str,
    vector_index_dir: str | Path,
    positive_gold: str | Path,
    candidate_index_version: str = XLSX_CANDIDATE_NAMESPACE,
    required_index_version: str | None = None,
    combined_retrieval_enabled: bool = False,
) -> None:
    """Fail closed when official XLSX eval is routed outside the wrapper path."""

    if clean(track).upper() != "XLSX" or clean(eval_mode).lower() != "official":
        return
    if agent_orchestrator_enabled:
        raise XlsxPreSilverRiskError(
            "official XLSX eval uses the XLSX wrapper/retrieval-evidence path only; "
            "generic AGENT/orchestrator routing is forbidden"
        )
    if combined_retrieval_enabled:
        raise XlsxPreSilverRiskError(
            "official XLSX eval uses the XLSX wrapper/retrieval-evidence path only; "
            "combined retrieval is disabled for gold evaluation"
        )
    if clean(retrieval_backend).lower() != "vector":
        raise XlsxPreSilverRiskError(
            "official XLSX eval uses vector XLSX candidate retrieval only; "
            f"retrieval_backend={retrieval_backend!r} is not allowed"
        )
    if clean(namespace) != XLSX_CANDIDATE_NAMESPACE:
        raise XlsxPreSilverRiskError(
            "official XLSX eval requires XLSX namespace "
            f"{XLSX_CANDIDATE_NAMESPACE}; got {namespace!r}"
        )
    if clean(candidate_index_version) != XLSX_CANDIDATE_NAMESPACE:
        raise XlsxPreSilverRiskError(
            "official XLSX eval requires XLSX candidate_index_version "
            f"{XLSX_CANDIDATE_NAMESPACE}; got {candidate_index_version!r}"
        )
    resolved_required_index_version = required_index_version or candidate_index_version
    if clean(resolved_required_index_version) != XLSX_CANDIDATE_NAMESPACE:
        raise XlsxPreSilverRiskError(
            "official XLSX eval requires XLSX required_index_version "
            f"{XLSX_CANDIDATE_NAMESPACE}; got {resolved_required_index_version!r}"
        )
    vector_path = resolve_ai_worker_path(vector_index_dir).resolve()
    if vector_path != CANONICAL_XLSX_CANDIDATE_INDEX_DIR:
        raise XlsxPreSilverRiskError(
            "official XLSX eval requires the XLSX candidate index directory "
            f"{XLSX_CANDIDATE_INDEX_DIR.as_posix()}; got {repo_relative(vector_path)!r}"
        )
    positive_path = resolve_ai_worker_path(positive_gold).resolve()
    if positive_path != CANONICAL_XLSX_RETRIEVAL_GOLD_PATH:
        raise XlsxPreSilverRiskError(
            "official XLSX eval requires the canonical current human-review retrieval/evidence "
            f"projection {repo_relative(CANONICAL_XLSX_RETRIEVAL_GOLD_PATH)}; got {repo_relative(positive_path)!r}"
        )


def validate_diagnostic_agentic_xlsx_config(
    *,
    eval_mode: str,
    track: str,
    namespace: str,
    agent_orchestrator_enabled: bool,
    diagnostic_agentic_allow: bool,
    retriever_names: Sequence[str] = (),
    global_fallback_enabled: bool = False,
    external_search_enabled: bool = False,
    max_iterations: int = 1,
) -> None:
    """Validate the explicit diagnostic-only agentic XLSX smoke path."""

    if agent_orchestrator_enabled and not diagnostic_agentic_allow:
        raise XlsxPreSilverRiskError(
            "diagnostic XLSX agentic E2E requires an explicit allow flag; "
            "official XLSX eval must keep using the wrapper/retrieval-evidence path"
        )
    if not agent_orchestrator_enabled:
        return
    if clean(eval_mode).lower() != "diagnostic":
        raise XlsxPreSilverRiskError("agentic XLSX E2E is diagnostic-only")
    if clean(track).upper() != "XLSX":
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop lost track=XLSX")
    if clean(namespace) != XLSX_CANDIDATE_NAMESPACE:
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop lost the XLSX namespace")
    if global_fallback_enabled:
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop cannot use global fallback retrieval")
    if external_search_enabled:
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop cannot use external search")
    if max_iterations < 1 or max_iterations > 5:
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop must have bounded max_iterations in [1, 5]")
    bad = [
        name
        for name in retriever_names
        if any(marker in clean(name).lower() for marker in FORBIDDEN_AGENTIC_RETRIEVER_MARKERS)
    ]
    if bad:
        raise XlsxPreSilverRiskError(
            "diagnostic agentic XLSX loop cannot call global/TEXT/PDF retrievers: "
            + ", ".join(bad)
        )


def validate_agentic_iteration_record(record: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_AGENTIC_ITERATION_FIELDS if field not in record]
    if missing:
        raise XlsxPreSilverRiskError("agentic iteration record missing fields: " + ", ".join(missing))
    validate_diagnostic_agentic_xlsx_config(
        eval_mode=clean(record.get("eval_mode")),
        track=clean(record.get("track")),
        namespace=clean(record.get("namespace")),
        agent_orchestrator_enabled=True,
        diagnostic_agentic_allow=True,
        retriever_names=[clean(record.get("retriever_or_tool_name"))],
        global_fallback_enabled=parse_bool(record.get("global_fallback_used")),
        external_search_enabled=parse_bool(record.get("external_search_used")),
        max_iterations=int(record.get("max_iterations") or 1),
    )
    if not isinstance(record.get("candidate_ids"), list):
        raise XlsxPreSilverRiskError("agentic iteration candidate_ids must be a list")
    if not isinstance(record.get("selected_context_ids"), list):
        raise XlsxPreSilverRiskError("agentic iteration selected_context_ids must be a list")
    if clean(record.get("action_type")).lower() in {"external_search", "web_search"}:
        raise XlsxPreSilverRiskError("diagnostic agentic XLSX loop cannot call external search tools")
    if not clean(record.get("stop_reason")):
        raise XlsxPreSilverRiskError("agentic iteration stop_reason must be recorded")


def resolve_current_xlsx_human_review_artifacts(
    *,
    registry_path: str | Path = OFFICIAL_REGISTRY,
    require_source_snapshot: bool = False,
) -> dict[str, Any]:
    """Resolve and hash-check the current 50/23/23 XLSX human-review artifacts."""

    registry = load_json(resolve_input_path(registry_path))
    defaults = registry.get("current_defaults") if isinstance(registry.get("current_defaults"), Mapping) else {}
    xlsx_default = defaults.get("track_a_xlsx") if isinstance(defaults.get("track_a_xlsx"), Mapping) else {}
    if clean(xlsx_default.get("denominator_key")) != CURRENT_XLSX_DENOMINATOR_KEY:
        raise XlsxPreSilverRiskError("registry current_defaults.track_a_xlsx does not point to the 23-row human-review denominator")

    denominators = registry.get("official_diagnostic_denominators")
    if not isinstance(denominators, Mapping):
        raise XlsxPreSilverRiskError("registry missing official_diagnostic_denominators")
    current = denominators.get(CURRENT_XLSX_DENOMINATOR_KEY)
    if not isinstance(current, Mapping):
        raise XlsxPreSilverRiskError(f"registry missing {CURRENT_XLSX_DENOMINATOR_KEY}")

    legacy = denominators.get(LEGACY_XLSX_V3_DENOMINATOR_KEY)
    if isinstance(legacy, Mapping):
        if parse_bool(legacy.get("current_default")):
            raise XlsxPreSilverRiskError("legacy 35-row XLSX v3 denominator is still marked current_default")
        if clean(legacy.get("superseded_by")) != CURRENT_XLSX_DENOMINATOR_KEY:
            raise XlsxPreSilverRiskError("legacy 35-row XLSX v3 denominator is not explicitly superseded")

    normalized_path = resolve_registry_artifact_path(current.get("path"), CURRENT_NORMALIZED_REPO_PATH)
    official_path = resolve_registry_artifact_path(current.get("official_positive_subset_path"), CURRENT_OFFICIAL_REPO_PATH)
    retrieval_path = resolve_registry_artifact_path(
        current.get("official_positive_retrieval_subset_path"),
        CURRENT_RETRIEVAL_REPO_PATH,
    )
    normalization_report_path = resolve_registry_artifact_path(
        current.get("normalization_report"),
        CURRENT_NORMALIZATION_REPORT_REPO_PATH,
    )

    checks = {
        "normalized": check_file_hash(normalized_path, clean(current.get("sha256"))),
        "official_positive": check_file_hash(official_path, clean(current.get("official_positive_subset_sha256"))),
        "official_positive_retrieval": check_file_hash(
            retrieval_path,
            clean(current.get("official_positive_retrieval_subset_sha256")),
        ),
        "normalization_report": artifact_entry(normalization_report_path),
    }

    normalized_rows = read_csv_rows(normalized_path)
    official_rows = read_csv_rows(official_path)
    retrieval_rows = read_csv_rows(retrieval_path)
    if len(normalized_rows) != EXPECTED_NORMALIZED_ROW_COUNT:
        raise XlsxPreSilverRiskError(f"normalized XLSX row count must be 50; got {len(normalized_rows)}")
    if len(official_rows) != EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT:
        raise XlsxPreSilverRiskError(f"official XLSX positive row count must be 23; got {len(official_rows)}")
    if len(retrieval_rows) != EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT:
        raise XlsxPreSilverRiskError(f"official XLSX retrieval row count must be 23; got {len(retrieval_rows)}")
    answer_denominator = current.get("official_xlsx_answer_generation_denominator")
    if int(answer_denominator if answer_denominator is not None else -1) != EXPECTED_XLSX_ANSWER_DENOMINATOR:
        raise XlsxPreSilverRiskError("XLSX answer-generation denominator must remain 0")

    official_ids = {clean(row.get("query_id")) for row in official_rows}
    if any("silver" in query_id.lower() for query_id in official_ids):
        raise XlsxPreSilverRiskError("official XLSX denominator cannot include silver rows")
    by_id = {clean(row.get("query_id")): row for row in normalized_rows}
    for query_id in SPECIAL_NON_OFFICIAL_QUERY_IDS:
        row = by_id.get(query_id)
        if not row:
            raise XlsxPreSilverRiskError(f"special row missing from normalized artifact: {query_id}")
        if parse_bool(row.get("include_in_official_positive_denominator")) or query_id in official_ids:
            raise XlsxPreSilverRiskError(f"special row must remain non-official: {query_id}")

    source_snapshot = {}
    if normalization_report_path.exists():
        normalization_report = load_json(normalization_report_path)
        source_review_pack = normalization_report.get("source_review_pack")
        if isinstance(source_review_pack, Mapping):
            snapshot_path = resolve_repo_relative_path(source_review_pack.get("snapshot_path"))
            if snapshot_path.exists():
                source_snapshot = check_file_hash(snapshot_path, clean(source_review_pack.get("sha256")))
            elif require_source_snapshot:
                raise XlsxPreSilverRiskError(f"source snapshot missing: {snapshot_path}")
    elif require_source_snapshot:
        raise XlsxPreSilverRiskError(f"normalization report missing: {normalization_report_path}")

    return {
        "denominator_key": CURRENT_XLSX_DENOMINATOR_KEY,
        "normalized_row_count": len(normalized_rows),
        "official_positive_row_count": len(official_rows),
        "official_positive_retrieval_row_count": len(retrieval_rows),
        "official_xlsx_answer_generation_denominator": 0,
        "artifacts": checks,
        "source_snapshot": source_snapshot,
        "special_non_official_query_ids": sorted(SPECIAL_NON_OFFICIAL_QUERY_IDS),
        "legacy_v3_superseded": True,
        "no_silver_rows_in_official_denominator": True,
    }


def silver_generation_requires_strict_preflight_status(report: Mapping[str, Any]) -> bool:
    if clean(report.get("status")) != STRICT_APPROVAL_STATUS:
        return False
    retrieval_denominator = report.get("official_xlsx_retrieval_evidence_denominator")
    if int(retrieval_denominator if retrieval_denominator is not None else -1) != EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT:
        return False
    answer_denominator = report.get("official_xlsx_answer_generation_denominator")
    if int(answer_denominator if answer_denominator is not None else -1) != 0:
        return False
    if parse_bool(report.get("diagnostic_llm_metric_included_in_official")):
        return False
    if parse_bool(report.get("generic_agent_orchestrator_allowed_for_official_xlsx")):
        return False
    return True


def assert_silver_generation_allowed(report: Mapping[str, Any]) -> None:
    if not silver_generation_requires_strict_preflight_status(report):
        raise XlsxPreSilverRiskError(
            "XLSX silver generation requires status "
            f"{STRICT_APPROVAL_STATUS} with denominator 23/0 and no official AGENT/LLM metric leakage"
        )


def check_file_hash(path: Path, expected_sha256: str) -> dict[str, Any]:
    entry = artifact_entry(path)
    if not path.exists():
        raise XlsxPreSilverRiskError(f"artifact missing: {path}")
    if not expected_sha256:
        raise XlsxPreSilverRiskError(f"registry hash missing for {repo_relative(path)}")
    if expected_sha256 and entry["sha256"] != expected_sha256:
        raise XlsxPreSilverRiskError(
            f"artifact hash mismatch for {repo_relative(path)}: expected {expected_sha256}, got {entry['sha256']}"
        )
    entry["expected_sha256"] = expected_sha256
    entry["hash_matches_registry"] = bool(expected_sha256 and entry["sha256"] == expected_sha256)
    return entry


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise XlsxPreSilverRiskError(f"JSON artifact missing: {path}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise XlsxPreSilverRiskError(f"JSON artifact must contain an object: {path}")
    return parsed


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise XlsxPreSilverRiskError(f"CSV artifact missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_input_path(value: object) -> Path:
    path = Path(clean(value))
    if not path:
        raise XlsxPreSilverRiskError("empty artifact path")
    if path.is_absolute():
        return path
    return ROOT / path


def resolve_ai_worker_path(value: object) -> Path:
    path = Path(clean(value))
    if not path:
        raise XlsxPreSilverRiskError("empty XLSX eval path")
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return ROOT / path
    return AI_WORKER / path


def resolve_repo_relative_path(value: object) -> Path:
    path = Path(clean(value))
    if not path:
        raise XlsxPreSilverRiskError("empty artifact path")
    if path.is_absolute():
        raise XlsxPreSilverRiskError(f"artifact path must be repo-relative, got absolute path: {path}")
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise XlsxPreSilverRiskError(f"artifact path escapes repository: {path}") from exc
    return resolved


def resolve_registry_artifact_path(value: object, expected_repo_path: str) -> Path:
    text = clean(value).replace("\\", "/")
    if text != expected_repo_path:
        raise XlsxPreSilverRiskError(
            f"registry artifact path must be canonical {expected_repo_path}; got {clean(value)!r}"
        )
    return resolve_repo_relative_path(text)


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y", "on"}


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
