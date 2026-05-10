"""Report-only optuna-round-refinement readiness for answer recovery."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_JSON = REPORT_DIR / "answer_recovery_optuna_round_refinement_readiness.json"
DEFAULT_MD = REPORT_DIR / "answer_recovery_optuna_round_refinement_readiness.md"
DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_optuna_round_01_config.yaml"
DEFAULT_CANDIDATE_REPORT = REPORT_DIR / "answer_recovery_fresh_diagnostic_candidate_discovery.json"

LOCAL_SKILL_CANDIDATES = [
    Path(r"C:\Users\sfr99\.agents\skills\optuna-round-refinement"),
    Path(r"C:\Users\sfr99\.codex\skills\refine"),
    Path(r"C:\Users\sfr99\.codex\skills\optuna-round-refinement"),
]

FORBIDDEN_SEARCH_PARAMS = {
    "allow_hidden_xlsx",
    "allow_pdf_file_content_support",
    "allow_diagnostic_only_support",
    "allow_unscoped_indexing",
    "mutate_production_index",
    "write_vectors",
    "create_namespace",
    "use_expected_answer_embedding",
    "use_label_embedding",
    "train_on_frozen_gold",
    "open_official_denominator",
    "promote_policy",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_readiness(
        config_path=resolve_path(args.config),
        candidate_report_path=resolve_path(args.candidate_report),
    )
    write_json(Path(args.json_out), payload)
    write_text(Path(args.md_out), render_md(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "integration_mode": payload["integration"]["recommended_mode"],
                "evaluate_callable_status": payload["evaluate_callable"]["status"],
                "schema_validation_status": payload["schema_validation"]["schema_validation_status"],
                "actual_round_execution_ready": payload["readiness"]["actual_round_execution_ready"],
                "diagnostic_optuna_smoke_only": payload["dry_run"]["diagnostic_optuna_smoke_only"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--candidate-report", default=str(DEFAULT_CANDIDATE_REPORT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args(argv)


def run_readiness(*, config_path: Path, candidate_report_path: Path) -> dict[str, Any]:
    skill_root = find_skill_root()
    repo_policy = inspect_repo_policy()
    deps = dependency_status()
    repo_presence = repo_local_presence()
    config = read_yaml(config_path) if config_path.exists() else {}
    candidate_report = read_json(candidate_report_path) if candidate_report_path.exists() else None
    schema_validation = validate_schema(config_path=config_path, config=config, skill_root=skill_root)
    evaluate_status = inspect_evaluate_callable(config.get("evaluate", ""))
    forbidden = sorted(set((config.get("search_space") or {}).keys()) & FORBIDDEN_SEARCH_PARAMS)
    reviewed_positive_count = int((candidate_report or {}).get("counts", {}).get("reviewed_positive_candidate_count") or 0)
    review_ready_count = int((candidate_report or {}).get("counts", {}).get("review_ready_count") or 0)
    guardrails = build_guardrails(candidate_report)
    objective_contract_available = evaluate_status["status"] == "importable" and not forbidden
    actual_ready = (
        objective_contract_available
        and schema_validation["schema_validation_status"] == "PASS"
        and reviewed_positive_count > 0
        and guardrails["all_guardrails_preserved"]
    )
    block_reasons = []
    if reviewed_positive_count <= 0:
        block_reasons.append("fresh_non_frozen_reviewed_positive_candidates_missing")
    if not objective_contract_available:
        block_reasons.append("evaluate_callable_or_config_contract_not_ready")
    if schema_validation["schema_validation_status"] != "PASS":
        block_reasons.append("schema_validation_not_passed")
    if not guardrails["all_guardrails_preserved"]:
        block_reasons.append("guardrail_uncertain_or_failed")

    return {
        "schema_version": "answer_recovery_optuna_round_refinement_readiness_report_v1",
        "status": "PASS",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "integration": {
            "optuna_round_refinement_present": skill_root is not None,
            "local_skill_path": str(skill_root) if skill_root else "",
            "repo_local_presence": repo_presence,
            "recommended_mode": "external",
            "vendor_deferred_reason": repo_policy["vendor_deferred_reason"],
            "skill_vendored": False,
            "skill_submodule": False,
            "skill_referenced_externally": skill_root is not None,
        },
        "dependencies": deps,
        "repo_policy": repo_policy,
        "existing_evaluate_callables": existing_evaluate_callables(),
        "evaluate_callable": evaluate_status,
        "config": {
            "path": repo_relative(config_path),
            "exists": config_path.exists(),
            "draft_status": "schema_oriented_not_execution_ready",
            "forbidden_search_params": forbidden,
            "n_trials": config.get("n_trials"),
            "direction": config.get("direction"),
            "objective_name": config.get("objective_name"),
            "evaluate": config.get("evaluate"),
        },
        "schema_validation": schema_validation,
        "candidate_prerequisites": {
            "candidate_report_path": repo_relative(candidate_report_path),
            "candidate_report_exists": candidate_report is not None,
            "review_ready_count": review_ready_count,
            "reviewed_positive_candidate_count": reviewed_positive_count,
            "fresh_non_frozen_reviewed_positive_candidates_exist": reviewed_positive_count > 0,
        },
        "readiness": {
            "wrapper_required": True,
            "safe_objective_contract_available": objective_contract_available,
            "safe_objective_currently_possible": reviewed_positive_count > 0,
            "actual_round_execution_ready": actual_ready,
            "reason": "" if actual_ready else "fresh_non_frozen_reviewed_positive_candidates_missing",
            "block_reasons": block_reasons,
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
        },
        "guardrail_status": guardrails,
        "dry_run": {
            "diagnostic_optuna_smoke_only": False,
            "skip_reason": "actual_round_execution_ready_false",
            "n_trials": 0,
            "promotion_evidence": False,
        },
        "llm_round_input": {
            "generated": False,
            "raw_data_included": False,
            "raw_data_exposed_to_llm_analyst": False,
            "reason": "No Optuna round or LLM input rendering was executed in this readiness step.",
        },
    }


def find_skill_root() -> Path | None:
    for path in LOCAL_SKILL_CANDIDATES:
        if (path / "SKILL.md").exists() and (path / "schemas" / "next_round_config.schema.json").exists():
            return path
    return None


def inspect_repo_policy() -> dict[str, Any]:
    agent_text = (REPO_ROOT / "AGENT.md").read_text(encoding="utf-8") if (REPO_ROOT / "AGENT.md").exists() else ""
    scripts_readme = (
        AI_WORKER_ROOT / "scripts" / "README.md"
    ).read_text(encoding="utf-8") if (AI_WORKER_ROOT / "scripts" / "README.md").exists() else ""
    return {
        "agent_file": "AGENT.md" if agent_text else "",
        "scripts_readme": "ai-worker/scripts/README.md" if scripts_readme else "",
        "external_artifact_policy_detected": "external runtime" in agent_text,
        "worker_scripts_canonical_detected": "ai-worker/scripts/" in scripts_readme,
        "vendor_deferred_reason": (
            "Repo already documents external runtime/tooling posture and existing eval/experiments README "
            "treats optuna-round-refinement orchestration/schema as skill-owned; use external skill reference."
        ),
    }


def repo_local_presence() -> dict[str, Any]:
    paths = [
        "third_party/optuna-round-refinement",
        "vendor/optuna-round-refinement",
        "tools/optuna-round-refinement",
    ]
    return {path: (REPO_ROOT / path).exists() for path in paths}


def dependency_status() -> dict[str, Any]:
    return {
        "optuna": import_status("optuna"),
        "jsonschema": import_status("jsonschema"),
        "pyyaml": import_status("yaml"),
    }


def import_status(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    return {"importable": spec is not None, "module": module_name}


def existing_evaluate_callables() -> list[dict[str, Any]]:
    return [
        {
            "path": "ai-worker/eval/tune_eval.py",
            "evaluate": "eval.tune_eval:evaluate",
            "suitable_for_answer_recovery": False,
            "reason": "Generic RAG eval harness bridge, not answer-recovery guarded objective.",
        },
        {
            "path": "ai-worker/eval/tune_eval_offline.py",
            "evaluate": "eval.tune_eval_offline:evaluate",
            "suitable_for_answer_recovery": False,
            "reason": "Legacy v3 offline tuning replay.",
        },
        {
            "path": "ai-worker/eval/tuning/answer_recovery_optuna_objective.py",
            "evaluate": "eval.tuning.answer_recovery_optuna_objective:evaluate",
            "suitable_for_answer_recovery": True,
            "reason": "Guarded report-only adapter that fails closed until reviewed candidates exist.",
        },
    ]


def inspect_evaluate_callable(spec: str) -> dict[str, Any]:
    if not spec or ":" not in spec:
        return {"spec": spec, "status": "missing", "callable": False, "error": "missing evaluate spec"}
    module_name, attr = spec.split(":", 1)
    if str(AI_WORKER_ROOT) not in sys.path:
        sys.path.insert(0, str(AI_WORKER_ROOT))
    try:
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
    except Exception as exc:  # pragma: no cover - report carries exact failure
        return {"spec": spec, "status": "import_failed", "callable": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"spec": spec, "status": "importable", "callable": callable(value), "error": ""}


def validate_schema(*, config_path: Path, config: Mapping[str, Any], skill_root: Path | None) -> dict[str, Any]:
    if not config_path.exists():
        return {
            "schema_validation_status": "DEFERRED",
            "schema_path": "",
            "command": "",
            "result": "config_missing",
            "failures": ["config_missing"],
        }
    if skill_root is None:
        return {
            "schema_validation_status": "DEFERRED",
            "schema_path": "",
            "command": "",
            "result": "optuna_round_refinement_schema_not_available",
            "failures": ["schema_not_available"],
        }
    schema_path = skill_root / "schemas" / "next_round_config.schema.json"
    if importlib.util.find_spec("jsonschema") is None:
        return {
            "schema_validation_status": "DEFERRED",
            "schema_path": str(schema_path),
            "command": f"python -c jsonschema.validate({repo_relative(config_path)})",
            "result": "jsonschema_not_importable",
            "failures": ["jsonschema_not_importable"],
        }
    try:
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(dict(config), schema)
    except Exception as exc:
        return {
            "schema_validation_status": "FAIL",
            "schema_path": str(schema_path),
            "command": f"jsonschema.validate({repo_relative(config_path)}, {schema_path})",
            "result": f"{type(exc).__name__}: {exc}",
            "failures": [str(exc)],
        }
    return {
        "schema_validation_status": "PASS",
        "schema_path": str(schema_path),
        "command": f"jsonschema.validate({repo_relative(config_path)}, {schema_path})",
        "result": "valid",
        "failures": [],
    }


def build_guardrails(candidate_report: Mapping[str, Any] | None) -> dict[str, Any]:
    candidate_guardrails = dict((candidate_report or {}).get("guardrail_status") or {})
    status = {
        "official_denominator_registry_changed": bool(candidate_guardrails.get("official_denominator_registry_changed")),
        "official_answer_denominator_opened": False,
        "production_index_mutation": False,
        "broad_indexing": False,
        "vector_write_attempted": False,
        "namespace_created": False,
        "frozen_gold_training_rows": 0,
        "frozen_gold_profile_selection": False,
        "expected_answer_or_label_embedding_count": 0,
        "hidden_xlsx_support_eligible_count": int(candidate_guardrails.get("hidden_xlsx_support_eligible_count") or 0),
        "pdf_file_content_mixing_support_eligible_count": int(
            candidate_guardrails.get("pdf_file_content_mixing_support_eligible_count") or 0
        ),
        "diagnostic_only_support_eligible_count": int(
            candidate_guardrails.get("diagnostic_only_support_eligible_count") or 0
        ),
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "promotion_evidence": False,
        "per_trial_llm_steering": False,
        "llm_as_objective": False,
        "mid_round_search_space_mutation": False,
        "raw_data_exposed_to_llm_analyst": False,
    }
    status["all_guardrails_preserved"] = (
        not status["official_denominator_registry_changed"]
        and status["hidden_xlsx_support_eligible_count"] == 0
        and status["pdf_file_content_mixing_support_eligible_count"] == 0
        and status["diagnostic_only_support_eligible_count"] == 0
    )
    return status


def render_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Optuna Round-Refinement Readiness",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Integration mode: `{payload['integration']['recommended_mode']}`.",
        f"- Skill present: `{payload['integration']['optuna_round_refinement_present']}`.",
        f"- Skill vendored: `{payload['integration']['skill_vendored']}`.",
        f"- Evaluate callable: `{payload['evaluate_callable']['spec']}` (`{payload['evaluate_callable']['status']}`).",
        f"- Config draft: `{payload['config']['path']}`.",
        f"- Schema validation: `{payload['schema_validation']['schema_validation_status']}`.",
        f"- Actual round execution ready: `{payload['readiness']['actual_round_execution_ready']}`.",
        f"- Reason: `{payload['readiness']['reason']}`.",
        f"- Diagnostic dry-run executed: `{payload['dry_run']['diagnostic_optuna_smoke_only']}`.",
        "",
        "## Dependencies",
        "",
    ]
    for name, status in payload["dependencies"].items():
        lines.append(f"- {name}: importable=`{status['importable']}`")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for reason in payload["readiness"]["block_reasons"]:
        lines.append(f"- `{reason}`")
    return "\n".join(lines) + "\n"


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
