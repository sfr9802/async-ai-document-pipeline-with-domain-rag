"""Diagnostic-only backend contract recheck for answer recovery embeddings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_answer_recovery_embedding_readiness as readiness  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = readiness.resolve_path(args.config)
    config = readiness.report_artifacts.with_reporting_overrides(
        readiness.load_config(config_path),
        readiness.report_artifacts.reporting_overrides_from_args(args),
    )
    validation_errors = readiness.validate_config(config)
    if validation_errors:
        raise ValueError("Unsafe embedding backend contract config: " + "; ".join(validation_errors))

    backend_contract_kwargs = {}
    if args.skip_backend_probe:
        backend_contract_kwargs["probe_embedding_allowed_override"] = False

    namespace_payload = readiness.discover_namespace_inventory(config)
    report = readiness.build_backend_contract_report(
        config=config,
        config_path=config_path,
        namespace_payload=namespace_payload,
        backend_contract_kwargs=backend_contract_kwargs,
    )
    readiness.write_backend_contract_outputs(config, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "backend_contract_status": report["backend_contract_status"],
                "embedding_backend_available": report["embedding_backend_available"],
                "staging_backfill_status": report["staging_backfill_status"],
                "backend_probe_embedding_succeeded": report["backend_probe_embedding_succeeded"],
                "backend_embedding_dimension_detected": report["backend_embedding_dimension_detected"],
                "vector_write_attempted": report["vector_write_attempted"],
                "namespace_created": report["namespace_created"],
                "production_mutation": report["production_mutation"],
                "official_denominator_opened": report["official_denominator_opened"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(readiness.DEFAULT_CONFIG))
    parser.add_argument(
        "--skip-backend-probe",
        action="store_true",
        help=(
            "Skip the live diagnostic query-embedding probe. This is for "
            "non-live smoke tests only; normal diagnostic runs should not use it."
        ),
    )
    readiness.report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
