"""Generate v2 PDF FILE lookup hard negatives from silver train rows only.

This is a deterministic report-only expansion step. It samples candidate file
identities only from silver PDF FILE lookup train rows, uses frozen gold values
only as exclusion guards, and keeps all generated rows TUNING_ONLY.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_silver_only_tuning_pass as silver_pass


DEFAULT_OUTPUT_CSV = AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning" / "silver_pdf_file_lookup_hard_negative_v2.csv"
DEFAULT_REPORT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "pdf_file_lookup_hard_negative_v2_report.json"
DEFAULT_REPORT_MD = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "pdf_file_lookup_hard_negative_v2_report.md"

CSV_FIELDS = [
    "query_id",
    "source_query_id",
    "query",
    "retrieval_lane",
    "expected_file_name",
    "source_file_name",
    "expected_document_version_id",
    "positive_expected_file_name",
    "positive_expected_document_version_id",
    "expected_evidence_policy",
    "negative_strategy",
    "silver_label",
    "silver_confidence",
    "denominator_role",
    "official_gold",
    "generation_reason",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = silver_pass.load_config(Path(args.config))
    output_csv = silver_pass.resolve_path(args.output_csv)
    report_json = silver_pass.resolve_path(args.report_json)
    report_md = silver_pass.resolve_path(args.report_md)
    rows, report = generate_hard_negatives(config, output_csv=output_csv)
    write_csv(output_csv, rows)
    silver_pass.write_json(report_json, report)
    silver_pass.write_text(report_md, render_report_md(report))
    print(
        json.dumps(
            {
                "status": report["status"],
                "row_count": report["counts"]["generated_row_count"],
                "output_csv": silver_pass.repo_relative(output_csv),
                "report_json": silver_pass.repo_relative(report_json),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(silver_pass.DEFAULT_CONFIG))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--report-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def generate_hard_negatives(config: Mapping[str, Any], *, output_csv: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = silver_pass.load_all_rows(config)
    silver_positive_rows = rows["silver_pdf_file_lookup_positive"]
    silver_hard_negative_rows = rows["silver_pdf_file_lookup_hard_negative"]
    frozen_positive_rows = rows["pdf_file_lookup_gold_positive"]
    frozen_diagnostic_rows = rows["pdf_file_lookup_diagnostic"]

    frozen_guard = frozen_exclusion_guard([frozen_positive_rows, frozen_diagnostic_rows])
    candidate_map = silver_identity_candidates([silver_positive_rows, silver_hard_negative_rows])
    generated: list[dict[str, str]] = []
    skipped = Counter()

    for positive in sorted(silver_positive_rows, key=lambda row: row.get("query_id", "")):
        positive_file = clean_identity(positive.get("expected_file_name") or positive.get("source_file_name"))
        positive_docv = silver_pass.clean(positive.get("expected_document_version_id"))
        if not positive_file:
            skipped["missing_positive_file_identity"] += 1
            continue
        if frozen_guard.contains_file(positive_file) or (positive_docv and frozen_guard.contains_document_version_id(positive_docv)):
            skipped["positive_identity_excluded_by_frozen_gold_guard"] += 1
            continue
        if frozen_guard.contains_query_or_id(positive):
            skipped["positive_query_or_id_excluded_by_frozen_gold_guard"] += 1
            continue

        for candidate in sorted(candidate_map.values(), key=lambda item: item["file_name"]):
            negative_file = candidate["file_name"]
            negative_docv = candidate.get("document_version_id", "")
            if negative_file == positive_file:
                continue
            if frozen_guard.contains_file(negative_file) or (
                negative_docv and frozen_guard.contains_document_version_id(negative_docv)
            ):
                skipped["negative_identity_excluded_by_frozen_gold_guard"] += 1
                continue
            strategy = classify_negative_strategy(positive_file, positive_docv, negative_file, negative_docv)
            generated.append(
                {
                    "query_id": f"silver_pdf_file_hneg_v2_{len(generated) + 1:04d}",
                    "source_query_id": silver_pass.clean(positive.get("query_id") or positive.get("source_query_id")),
                    "query": silver_pass.clean(positive.get("query")),
                    "retrieval_lane": "pdf_file_lookup",
                    "expected_file_name": negative_file,
                    "source_file_name": negative_file,
                    "expected_document_version_id": negative_docv,
                    "positive_expected_file_name": positive_file,
                    "positive_expected_document_version_id": positive_docv,
                    "expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
                    "negative_strategy": strategy,
                    "silver_label": "SILVER_FILE_LOOKUP_HARD_NEGATIVE_V2",
                    "silver_confidence": "MEDIUM",
                    "denominator_role": "TUNING_ONLY",
                    "official_gold": "false",
                    "generation_reason": "silver-only PDF file identity hard negative; no content/page/bbox/table/row/column/value success claimed",
                }
            )

    strategy_counts = Counter(row["negative_strategy"] for row in generated)
    report = {
        "schema_version": "pdf_file_lookup_hard_negative_v2_report_v1",
        "status": "PASS",
        "generated_at": silver_pass.utc_timestamp(),
        "output_csv": silver_pass.repo_relative(output_csv),
        "policy": {
            "source_rows": "silver_pdf_file_lookup_train_rows_only",
            "frozen_gold_values_used_for_sampling": False,
            "frozen_gold_values_used_for_exclusion_guard_only": True,
            "frozen_gold_identity_values_materialized_in_output": False,
            "denominator_role": "TUNING_ONLY",
            "official_gold": False,
            "pdf_file_lookup_semantics": "file_identity_only",
            "content_success_claimed": False,
            "page_success_claimed": False,
            "bbox_success_claimed": False,
            "table_success_claimed": False,
            "row_success_claimed": False,
            "column_success_claimed": False,
            "value_success_claimed": False,
            "official_denominator_registry_changed": False,
            "production_index_mutation": False,
            "broad_indexing": False,
        },
        "inputs": {
            "silver_positive": config["input_silver_train_files"]["pdf_file_lookup_positive"],
            "silver_hard_negative_v1": config["input_silver_train_files"]["pdf_file_lookup_hard_negative"],
            "frozen_gold_positive": "used_for_exclusion_count_only",
            "frozen_gold_diagnostic": "used_for_exclusion_count_only",
        },
        "counts": {
            "silver_positive_row_count": len(silver_positive_rows),
            "silver_train_identity_candidate_count": len(candidate_map),
            "generated_row_count": len(generated),
            "frozen_gold_file_identity_exclusion_count": len(frozen_guard.file_names),
            "frozen_gold_document_version_id_exclusion_count": len(frozen_guard.document_version_ids),
            "skipped": dict(sorted(skipped.items())),
        },
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "strategy_support": {
            "similar_file_names": strategy_counts.get("similar_file_name_wrong_identity", 0)
            + strategy_counts.get("same_metadata_family_wrong_file_identity", 0),
            "generic_filename_patterns": strategy_counts.get("generic_filename_wrong_identity", 0),
            "same_metadata_family": strategy_counts.get("same_metadata_family_wrong_file_identity", 0),
            "wrong_document_version_id": strategy_counts.get("wrong_document_version_id", 0),
            "wrong_document_version_id_note": (
                "No silver-only mismatched document_version_id pairs were available."
                if strategy_counts.get("wrong_document_version_id", 0) == 0
                else "Generated from silver-only mismatched document_version_id pairs."
            ),
        },
        "validation": {
            "generated_rows_are_tuning_only": all(row["denominator_role"] == "TUNING_ONLY" for row in generated),
            "generated_rows_official_gold_false": all(row["official_gold"] == "false" for row in generated),
            "generated_rows_exclude_frozen_gold_file_identities": all(
                not frozen_guard.contains_file(row["expected_file_name"])
                and not frozen_guard.contains_file(row["positive_expected_file_name"])
                for row in generated
            ),
            "generated_rows_exclude_frozen_gold_document_version_ids": all(
                not frozen_guard.contains_document_version_id(row["expected_document_version_id"])
                and not frozen_guard.contains_document_version_id(row["positive_expected_document_version_id"])
                for row in generated
            ),
            "generated_queries_exclude_frozen_gold_query_text": all(
                not frozen_guard.contains_query(row["query"]) for row in generated
            ),
        },
    }
    return generated, report


class FrozenExclusionGuard:
    def __init__(self, *, file_names: set[str], document_version_ids: set[str], queries: set[str], ids: set[str]) -> None:
        self.file_names = file_names
        self.document_version_ids = document_version_ids
        self.queries = queries
        self.ids = ids

    def contains_file(self, value: str) -> bool:
        return clean_identity(value) in self.file_names

    def contains_document_version_id(self, value: str) -> bool:
        value = silver_pass.clean(value)
        return bool(value and value in self.document_version_ids)

    def contains_query(self, value: str) -> bool:
        value = normalize_text(value)
        return bool(value and value in self.queries)

    def contains_query_or_id(self, row: Mapping[str, str]) -> bool:
        ids = {silver_pass.clean(row.get("query_id")), silver_pass.clean(row.get("source_query_id"))}
        return bool((ids & self.ids) or self.contains_query(row.get("query", "")))


def frozen_exclusion_guard(row_lists: Iterable[Sequence[Mapping[str, str]]]) -> FrozenExclusionGuard:
    file_names: set[str] = set()
    document_version_ids: set[str] = set()
    queries: set[str] = set()
    ids: set[str] = set()
    for rows in row_lists:
        for row in rows:
            for key in ("expected_file_name", "source_file_name", "positive_expected_file_name"):
                value = clean_identity(row.get(key))
                if value:
                    file_names.add(value)
            docv = silver_pass.clean(row.get("expected_document_version_id"))
            if docv:
                document_version_ids.add(docv)
            query = normalize_text(row.get("query"))
            if query:
                queries.add(query)
            for key in ("query_id", "source_query_id"):
                value = silver_pass.clean(row.get(key))
                if value:
                    ids.add(value)
    return FrozenExclusionGuard(
        file_names=file_names,
        document_version_ids=document_version_ids,
        queries=queries,
        ids=ids,
    )


def silver_identity_candidates(row_lists: Iterable[Sequence[Mapping[str, str]]]) -> dict[str, dict[str, str]]:
    candidates: dict[str, dict[str, str]] = {}
    for rows in row_lists:
        for row in rows:
            docv = silver_pass.clean(row.get("expected_document_version_id"))
            for key in ("expected_file_name", "source_file_name", "positive_expected_file_name"):
                file_name = clean_identity(row.get(key))
                if not file_name:
                    continue
                candidates.setdefault(
                    file_name,
                    {
                        "file_name": file_name,
                        "document_version_id": docv,
                    },
                )
                if docv and not candidates[file_name].get("document_version_id"):
                    candidates[file_name]["document_version_id"] = docv
    return candidates


def classify_negative_strategy(positive_file: str, positive_docv: str, negative_file: str, negative_docv: str) -> str:
    if positive_file == negative_file and positive_docv and negative_docv and positive_docv != negative_docv:
        return "wrong_document_version_id"
    if is_generic_filename(positive_file) or is_generic_filename(negative_file):
        return "generic_filename_wrong_identity"
    positive_features = silver_pass.file_features(positive_file)
    negative_features = silver_pass.file_features(negative_file)
    if positive_features["families"] & negative_features["families"]:
        return "same_metadata_family_wrong_file_identity"
    if identities_are_similar(positive_features, negative_features):
        return "similar_file_name_wrong_identity"
    return "silver_train_other_file_identity"


def identities_are_similar(positive_features: Mapping[str, set[str]], negative_features: Mapping[str, set[str]]) -> bool:
    return bool(
        (positive_features["years"] & negative_features["years"])
        or (positive_features["months"] & negative_features["months"])
        or (positive_features["tokens"] & negative_features["tokens"])
    )


def is_generic_filename(name: str) -> bool:
    stem = Path(name).stem.lower()
    return bool(re.fullmatch(r"file(?:\s*\(\d+\))?", stem))


def normalize_text(value: Any) -> str:
    return " ".join(silver_pass.clean(value).split()).lower()


def clean_identity(value: Any) -> str:
    return silver_pass.clean(value)


def write_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def render_report_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    policy = payload["policy"]
    lines = [
        "# PDF FILE Lookup Hard Negative V2 Report",
        "",
        f"- Status: `{payload['status']}`.",
        "- Source rows: `silver_pdf_file_lookup_train_rows_only`.",
        "- Frozen gold values used for sampling: `false`.",
        "- Frozen gold values used only as exclusion guards: `true`.",
        f"- Output CSV: `{payload['output_csv']}`.",
        "- PDF FILE lookup semantics: `file_identity_only`.",
        "- Content/page/bbox/table/row/column/value success claimed: `false`.",
        f"- Denominator role: `{policy['denominator_role']}`; official_gold: `{str(policy['official_gold']).lower()}`.",
        "",
        "## Counts",
        "",
        f"- Silver positive rows: `{counts['silver_positive_row_count']}`.",
        f"- Silver train identity candidates: `{counts['silver_train_identity_candidate_count']}`.",
        f"- Generated rows: `{counts['generated_row_count']}`.",
        f"- Frozen gold file identities excluded by guard: `{counts['frozen_gold_file_identity_exclusion_count']}`.",
        f"- Frozen gold document_version_id values excluded by guard: `{counts['frozen_gold_document_version_id_exclusion_count']}`.",
        "",
        "## Strategy Counts",
        "",
    ]
    if payload["strategy_counts"]:
        for strategy, count in payload["strategy_counts"].items():
            lines.append(f"- `{strategy}`: `{count}`")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Validation",
            "",
        ]
    )
    for key, value in payload["validation"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
