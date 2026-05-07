"""Shared helpers for supplemental elec/lh PDF diagnostics.

The supplemental pipeline is file-based and diagnostic-only. Helpers in this
module deliberately avoid DB, SearchUnit, indexing, retrieval, LLM, or
promotion side effects.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent
REPORT_DIR = AI_WORKER / "eval" / "reports" / "rag-ingestion"
EVAL_QUERIES_DIR = AI_WORKER / "eval" / "eval_queries"
REVIEW_DIR = AI_WORKER / "eval" / "review" / "pdf_supplemental_elec_lh"
ARTIFACT_ROOT = AI_WORKER / "eval" / "artifacts" / "eval_runs"

SOURCE_DIRECTORIES = [
    "ai-worker/eval/datasets/elec",
    "ai-worker/eval/datasets/lh",
]

PROTECTED_SOURCE_SHA256: dict[str, str] = {
    "ai-worker/eval/eval_queries/gold_queries_pdf_v0.csv": "cf582fbf0629962ba035ad121d4e9dd7fbea2ee4b7251c51dce2a0a31ea22e29",
    "ai-worker/eval/eval_queries/gold_queries_pdf_v1_review_draft.csv": "5bea29e2ba1bd1787e37afdfd4c42b350773eb8ebab87a4041f280ab45f9b694",
}
PROTECTED_REGISTRY_PATHS = {"ai-worker/eval/eval_queries/official_denominator_registry.json"}

PROTECTED_OUTPUT_FILENAMES = {Path(path).name.lower() for path in PROTECTED_SOURCE_SHA256}
PROTECTED_OUTPUT_FILENAMES.update(Path(path).name.lower() for path in PROTECTED_REGISTRY_PATHS)

COMMON_GUARDRAILS: dict[str, Any] = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "official_denominator_changed": False,
    "codex_gold_policy_decision_applied": False,
    "pdf_c7_policy_decision_applied": False,
    "synthetic_diagnostic_only": True,
    "xlsx_scope_excluded": True,
    "pdf_scope_only": True,
    "external_cloud_llm_run": False,
    "live_llm_answer_generation_run": False,
    "optional_judge_run": False,
    "retrieval_tuning_applied": False,
    "reranking_applied": False,
    "parser_expansion_applied": False,
    "threshold_relaxation_applied": False,
    "db_mutation_applied": False,
    "searchunit_mutation_applied": False,
    "candidate_artifact_changed": False,
    "immutable_baseline_changed": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_not_claimed": True,
}

LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\]|::1)(:\d+)?(/|$)", re.IGNORECASE)
EXTERNAL_KEY_ENV_RE = re.compile(
    r"(OPENAI|ANTHROPIC|GOOGLE|GEMINI|MISTRAL|COHERE|TOGETHER|GROQ|VOYAGE|AZURE).*API.*KEY",
    re.IGNORECASE,
)
PLACEHOLDER_VALUES = {"", "none", "null", "changeme", "placeholder", "dummy", "test", "local"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id(prefix: str = "") -> str:
    value = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}{value}" if prefix else value


def artifact_dir_for(run_id_value: str) -> Path:
    return ARTIFACT_ROOT / f"pdf_supplemental_elec_lh_{run_id_value}"


def latest_supplemental_artifact_dir() -> Path:
    candidates = sorted(
        ARTIFACT_ROOT.glob("pdf_supplemental_elec_lh_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No pdf_supplemental_elec_lh artifact directory found")
    return candidates[0].resolve()


def resolve_path(path: Path | str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value.resolve()
    for candidate in (Path.cwd() / value, AI_WORKER / value, ROOT / value):
        if candidate.exists():
            return candidate.resolve()
    parts = value.parts
    if parts and parts[0] == "ai-worker":
        return (ROOT / value).resolve()
    if parts and parts[0] == "eval":
        return (AI_WORKER / value).resolve()
    return (Path.cwd() / value).resolve()


def display_path(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {display_path(path)}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    ensure_parent(path)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield payload


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_source_status() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for relative_path, expected_sha256 in PROTECTED_SOURCE_SHA256.items():
        path = (ROOT / relative_path).resolve()
        exists = path.exists()
        actual_sha256 = sha256_file(path).lower() if exists else None
        result[relative_path] = {
            "path": relative_path,
            "exists": exists,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "matches_expected": bool(exists and actual_sha256 == expected_sha256),
        }
    for relative_path in PROTECTED_REGISTRY_PATHS:
        path = (ROOT / relative_path).resolve()
        exists = path.exists()
        actual_sha256 = sha256_file(path).lower() if exists else None
        registry_status = validate_denominator_registry(path) if exists else {"ok": False, "errors": ["missing"]}
        result[relative_path] = {
            "path": relative_path,
            "exists": exists,
            "expected_sha256": None,
            "actual_sha256": actual_sha256,
            "matches_expected": bool(exists and registry_status["ok"]),
            "validation": registry_status,
        }
    return result


def protected_source_blockers() -> list[str]:
    blockers: list[str] = []
    for relative_path, status in protected_source_status().items():
        if not status["exists"]:
            blockers.append(f"protected source missing: {relative_path}")
        elif not status["matches_expected"]:
            validation = status.get("validation") if isinstance(status.get("validation"), Mapping) else {}
            if validation:
                blockers.append(f"protected registry validation failed: {relative_path}")
            else:
                blockers.append(f"protected source hash drift: {relative_path}")
    return blockers


def validate_denominator_registry(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except Exception as exc:
        return {"ok": False, "errors": [f"read_failed:{type(exc).__name__}"]}
    errors: list[str] = []
    denominators = payload.get("official_diagnostic_denominators")
    if not isinstance(denominators, Mapping):
        errors.append("missing_official_diagnostic_denominators")
        denominators = {}
    defaults = payload.get("current_defaults") if isinstance(payload.get("current_defaults"), Mapping) else {}
    track_a = defaults.get("track_a_xlsx") if isinstance(defaults.get("track_a_xlsx"), Mapping) else {}
    current_key = "track_a_xlsx_human_review_normalized_v0"
    if track_a.get("denominator_key") != current_key:
        errors.append("xlsx_current_default_not_human_review_v0")
    current = denominators.get(current_key)
    if not isinstance(current, Mapping):
        errors.append("missing_xlsx_human_review_denominator")
        current = {}
    if current.get("official_positive_denominator") != 23:
        errors.append("xlsx_official_positive_denominator_not_23")
    if current.get("official_xlsx_answer_generation_denominator") != 0:
        errors.append("xlsx_answer_generation_denominator_not_0")
    if not current.get("sha256") or not current.get("official_positive_retrieval_subset_sha256"):
        errors.append("xlsx_registry_hash_missing")
    legacy = denominators.get("track_a_xlsx_reviewed_positive")
    if isinstance(legacy, Mapping):
        if legacy.get("current_default") is not False:
            errors.append("legacy_xlsx_v3_not_marked_noncurrent")
        if legacy.get("superseded_by") != current_key:
            errors.append("legacy_xlsx_v3_not_superseded")
    return {
        "ok": not errors,
        "errors": errors,
        "schema_version": payload.get("schema_version"),
        "xlsx_current_default": track_a.get("denominator_key"),
    }


def supplemental_output_path_findings(path_by_label: Mapping[str, Path]) -> dict[str, list[str]]:
    protected_paths = {
        (ROOT / relative_path).resolve(): relative_path
        for relative_path in PROTECTED_SOURCE_SHA256
    }
    protected_paths.update(
        {
            (ROOT / relative_path).resolve(): relative_path
            for relative_path in PROTECTED_REGISTRY_PATHS
        }
    )
    allowed_roots = [
        REPORT_DIR.resolve(),
        EVAL_QUERIES_DIR.resolve(),
        REVIEW_DIR.resolve(),
        ARTIFACT_ROOT.resolve(),
    ]
    findings: dict[str, list[str]] = {}
    for label, path in path_by_label.items():
        resolved = path.resolve()
        reasons: list[str] = []
        display = display_path(resolved)
        lowered_display = display.lower()
        lowered_name = resolved.name.lower()
        if resolved in protected_paths:
            reasons.append(f"{label} would overwrite protected source: {protected_paths[resolved]}")
        if lowered_name in PROTECTED_OUTPUT_FILENAMES:
            reasons.append(f"{label} uses protected filename: {resolved.name}")
        if "supplemental" not in lowered_display:
            reasons.append(f"{label} path must be supplemental-specific: {display}")
        if not any(path_is_relative_to(resolved, root) for root in allowed_roots):
            reasons.append(f"{label} path must stay under eval reports, eval queries, review, or eval_runs: {display}")
        if reasons:
            findings[label] = reasons
    return findings


def supplemental_output_path_blockers(path_by_label: Mapping[str, Path]) -> list[str]:
    blockers: list[str] = []
    for reasons in supplemental_output_path_findings(path_by_label).values():
        blockers.extend(reasons)
    return blockers


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def source_for_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "elec" in parts:
        return "elec"
    if "lh" in parts:
        return "lh"
    return "unknown"


def relative_to_root(path: Path) -> str:
    return display_path(path)


def to_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def short_text(text: str, max_chars: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def text_stats(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": min(values),
        "median": median(values),
        "max": max(values),
    }


def table_like_score(text: str, bbox: list[float] | None = None) -> dict[str, Any]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    tokens = re.findall(r"[0-9A-Za-z가-힣.,%()/-]+", text or "")
    numeric_tokens = [token for token in tokens if re.search(r"\d", token)]
    separators = sum((text or "").count(token) for token in ("|", "\t", "  ", "·"))
    short_dense_lines = [line for line in lines if 3 <= len(re.findall(r"\S+", line)) <= 12 and len(line) <= 120]
    line_numeric_ratio = 0.0
    if lines:
        line_numeric_ratio = sum(1 for line in lines if re.search(r"\d", line)) / len(lines)
    token_numeric_ratio = (len(numeric_tokens) / len(tokens)) if tokens else 0.0
    score = 0
    reasons: list[str] = []
    if len(lines) >= 3 and len(short_dense_lines) / max(len(lines), 1) >= 0.5:
        score += 2
        reasons.append("short_token_grid")
    if token_numeric_ratio >= 0.25 and len(numeric_tokens) >= 4:
        score += 2
        reasons.append("numeric_column_density")
    if line_numeric_ratio >= 0.5 and len(lines) >= 2:
        score += 1
        reasons.append("aligned_numeric_lines")
    if separators >= 4:
        score += 1
        reasons.append("repeated_separators")
    if bbox and len(bbox) == 4 and (bbox[2] - bbox[0]) > 250 and len(lines) >= 2:
        score += 1
        reasons.append("wide_multi_line_block")
    return {
        "score": score,
        "is_table_like": score >= 3,
        "reasons": reasons,
        "numeric_token_ratio": round(token_numeric_ratio, 4),
        "line_numeric_ratio": round(line_numeric_ratio, 4),
        "line_count": len(lines),
        "token_count": len(tokens),
    }


def bbox_to_list(value: Any) -> list[float] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            nums = [to_float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", value)]
            nums = [item for item in nums if item is not None]
            return [float(item) for item in nums[:4]] if len(nums) >= 4 else None
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        parsed = [to_float(item) for item in value[:4]]
        if all(item is not None for item in parsed):
            return [float(item) for item in parsed if item is not None]
    return None


def bbox_key(value: Any) -> str:
    bbox = bbox_to_list(value)
    if not bbox:
        return ""
    return ",".join(f"{item:.2f}" for item in bbox)


def has_external_cloud_key(env: Mapping[str, str] | None = None) -> bool:
    env = env or os.environ
    for key, value in env.items():
        if not EXTERNAL_KEY_ENV_RE.search(key):
            continue
        normalized = str(value or "").strip().lower()
        if normalized not in PLACEHOLDER_VALUES:
            return True
    return False


def local_pageindex_preflight(*, allow_local_run: bool, model: str | None, base_url: str | None) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if not allow_local_run:
        blockers.append("Pass --allow-local-run to execute supplemental PageIndex locally.")
    if not model:
        blockers.append("--model is required for a local/open-source PageIndex run.")
    if not base_url or not LOCALHOST_RE.search(base_url):
        blockers.append("--base-url must be an explicit localhost OpenAI-compatible endpoint.")
    if has_external_cloud_key():
        blockers.append("External/cloud API key detected in environment; fail closed.")
    return not blockers, blockers


def sorted_counter(counter: Mapping[str, int]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def artifact_identity(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "exists": path.exists()}
