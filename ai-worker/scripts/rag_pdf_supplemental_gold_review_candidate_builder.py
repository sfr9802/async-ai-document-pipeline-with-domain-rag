"""Build diagnostic-only supplemental PDF gold-review candidates.

This script joins the existing supplemental elec/lh diagnostic artifacts by
query_id and assigns a conservative review_lane for human review. It does not
write or update official gold, denominator, promotion, DB, SearchUnit, index,
candidate, baseline, retrieval, reranking, parser, judge, or LLM artifacts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from rag_pdf_supplemental_common import (
    ARTIFACT_ROOT,
    COMMON_GUARDRAILS,
    EVAL_QUERIES_DIR,
    REPORT_DIR,
    artifact_identity,
    display_path,
    iter_jsonl,
    read_csv,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    truthy,
    utc_timestamp,
    write_csv,
    write_jsonl,
)


DEFAULT_ARTIFACT_DIR = ARTIFACT_ROOT / "pdf_supplemental_elec_lh_20260506T_supplemental_diag"
DEFAULT_SYNTHETIC_CSV = EVAL_QUERIES_DIR / "gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv"
DEFAULT_ANSWER_QUALITY_JSON = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.json"
DEFAULT_ANSWER_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_ABSTAIN_JSON = REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.json"
DEFAULT_ABSTAIN_CSV = REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.csv"
DEFAULT_FALSE_POSITIVE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"
DEFAULT_FALSE_POSITIVE_CSV = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.csv"
DEFAULT_LH_RECLASS_JSON = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_reclassification.json"
DEFAULT_LH_RECLASS_CSV = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_reclassification.csv"
DEFAULT_PRECISION_JSON = REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.json"
DEFAULT_PRECISION_CSV = REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.csv"
DEFAULT_CANARY_JSON = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_canary_readiness.json"
DEFAULT_CANARY_CSV = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_canary_readiness.csv"
DEFAULT_INVENTORY_JSON = REPORT_DIR / "rag_pdf_supplemental_elec_lh_inventory.json"
DEFAULT_EVIDENCE_JSONL = DEFAULT_ARTIFACT_DIR / "answer_evidence_objects.jsonl"
DEFAULT_DRAFT_JSONL = DEFAULT_ARTIFACT_DIR / "deterministic_answer_drafts.jsonl"

SCHEMA_VERSION = "pdf_supplemental_gold_review_candidate_builder_v1"

REVIEW_LANES = [
    "READY_SECTION_SUMMARY",
    "READY_EXTRACTIVE_CONTEXT",
    "READY_RESTRICTED_TABLE_CONTEXT",
    "HIGH_CONFIDENCE_TABLE_CANDIDATE",
    "ABSTAIN_TABLE_LIKE_NO_ROW_COLUMN_VALUE",
    "ABSTAIN_KEYWORD_OR_LABEL_ONLY",
    "ABSTAIN_GENERIC_SECTION_CONTEXT",
    "FALSE_POSITIVE_REFERENCE_CODE",
    "FALSE_POSITIVE_BULLET_OR_FORMULA",
    "FALSE_POSITIVE_NOISE",
    "OCR_NEEDED_UNSUPPORTED",
    "POLICY_OR_DIAGNOSTIC_ONLY",
]

CORE_GUARDRAIL_VALUES: dict[str, Any] = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "official_denominator_changed": False,
    "codex_gold_policy_decision_applied": False,
    "pdf_c7_policy_decision_applied": False,
    "external_cloud_llm_run": False,
    "live_llm_answer_generation_run": False,
    "optional_judge_run": False,
    "retrieval_tuning_applied": False,
    "reranking_applied": False,
    "parser_expansion_applied": False,
    "db_mutation_applied": False,
    "searchunit_mutation_applied": False,
    "candidate_artifact_changed": False,
    "immutable_baseline_changed": False,
    "bbox_contract_success_not_claimed": True,
}

OUTPUT_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "actual_llm_answer_generation_run": False,
    "actual_generated_answer_output": False,
    "answer_draft_is_actual_generated_llm_answer": False,
    "table_semantics_success_claimed": False,
    "row_column_value_semantics_claimed": False,
}

CANDIDATE_FIELDS = [
    "track",
    "query_id",
    "dataset",
    "source_file_name",
    "page_no",
    "page_label",
    "section_path",
    "query",
    "expected_evidence_excerpt",
    "evidence_object_summary",
    "deterministic_draft",
    "review_lane",
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "risk_tags",
    "diagnostic_reason",
]


class FailClosedInputError(RuntimeError):
    """Raised when a source artifact is missing or violates guardrails."""

    def __init__(self, blockers: list[str]):
        self.blockers = blockers
        super().__init__("; ".join(blockers))


@dataclass(frozen=True)
class CandidateInputPaths:
    synthetic_csv: Path = DEFAULT_SYNTHETIC_CSV
    answer_quality_json: Path = DEFAULT_ANSWER_QUALITY_JSON
    answer_quality_csv: Path = DEFAULT_ANSWER_QUALITY_CSV
    abstain_json: Path = DEFAULT_ABSTAIN_JSON
    abstain_csv: Path = DEFAULT_ABSTAIN_CSV
    false_positive_json: Path = DEFAULT_FALSE_POSITIVE_JSON
    false_positive_csv: Path = DEFAULT_FALSE_POSITIVE_CSV
    lh_reclassification_json: Path = DEFAULT_LH_RECLASS_JSON
    lh_reclassification_csv: Path = DEFAULT_LH_RECLASS_CSV
    precision_json: Path = DEFAULT_PRECISION_JSON
    precision_csv: Path = DEFAULT_PRECISION_CSV
    canary_json: Path = DEFAULT_CANARY_JSON
    canary_csv: Path = DEFAULT_CANARY_CSV
    inventory_json: Path = DEFAULT_INVENTORY_JSON
    evidence_jsonl: Path = DEFAULT_EVIDENCE_JSONL
    draft_jsonl: Path = DEFAULT_DRAFT_JSONL

    def resolved(self) -> "CandidateInputPaths":
        return CandidateInputPaths(**{key: resolve_path(value) for key, value in self.as_dict().items()})

    def as_dict(self) -> dict[str, Path]:
        return {
            "synthetic_csv": self.synthetic_csv,
            "answer_quality_json": self.answer_quality_json,
            "answer_quality_csv": self.answer_quality_csv,
            "abstain_json": self.abstain_json,
            "abstain_csv": self.abstain_csv,
            "false_positive_json": self.false_positive_json,
            "false_positive_csv": self.false_positive_csv,
            "lh_reclassification_json": self.lh_reclassification_json,
            "lh_reclassification_csv": self.lh_reclassification_csv,
            "precision_json": self.precision_json,
            "precision_csv": self.precision_csv,
            "canary_json": self.canary_json,
            "canary_csv": self.canary_csv,
            "inventory_json": self.inventory_json,
            "evidence_jsonl": self.evidence_jsonl,
            "draft_jsonl": self.draft_jsonl,
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = CandidateInputPaths(
        synthetic_csv=Path(args.synthetic_csv),
        answer_quality_json=Path(args.answer_quality_json),
        answer_quality_csv=Path(args.answer_quality_csv),
        abstain_json=Path(args.abstain_json),
        abstain_csv=Path(args.abstain_csv),
        false_positive_json=Path(args.false_positive_json),
        false_positive_csv=Path(args.false_positive_csv),
        lh_reclassification_json=Path(args.lh_reclassification_json),
        lh_reclassification_csv=Path(args.lh_reclassification_csv),
        precision_json=Path(args.precision_json),
        precision_csv=Path(args.precision_csv),
        canary_json=Path(args.canary_json),
        canary_csv=Path(args.canary_csv),
        inventory_json=Path(args.inventory_json),
        evidence_jsonl=Path(args.evidence_jsonl),
        draft_jsonl=Path(args.draft_jsonl),
    )
    output_csv = resolve_path(args.output_csv) if args.output_csv else None
    output_jsonl = resolve_path(args.output_jsonl) if args.output_jsonl else None
    blockers = supplemental_output_path_blockers({
        key: path for key, path in {"output_csv": output_csv, "output_jsonl": output_jsonl}.items() if path
    })
    if blockers:
        print(json.dumps({"status": "FAIL_CLOSED_UNSAFE_OUTPUT_PATH", "blockers": blockers}, ensure_ascii=False, indent=2))
        return 2
    try:
        payload = build_candidate_dataset(paths=paths, expected_source_rows=args.expected_source_rows)
    except FailClosedInputError as exc:
        print(json.dumps({"status": "FAIL_CLOSED_INPUT_ERROR", "blockers": exc.blockers}, ensure_ascii=False, indent=2))
        return 2
    if output_csv:
        write_csv(output_csv, payload["rows"], CANDIDATE_FIELDS)
    if output_jsonl:
        write_jsonl(output_jsonl, payload["rows"])
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0 if payload["summary"]["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-csv", default=str(DEFAULT_SYNTHETIC_CSV))
    parser.add_argument("--answer-quality-json", default=str(DEFAULT_ANSWER_QUALITY_JSON))
    parser.add_argument("--answer-quality-csv", default=str(DEFAULT_ANSWER_QUALITY_CSV))
    parser.add_argument("--abstain-json", default=str(DEFAULT_ABSTAIN_JSON))
    parser.add_argument("--abstain-csv", default=str(DEFAULT_ABSTAIN_CSV))
    parser.add_argument("--false-positive-json", default=str(DEFAULT_FALSE_POSITIVE_JSON))
    parser.add_argument("--false-positive-csv", default=str(DEFAULT_FALSE_POSITIVE_CSV))
    parser.add_argument("--lh-reclassification-json", default=str(DEFAULT_LH_RECLASS_JSON))
    parser.add_argument("--lh-reclassification-csv", default=str(DEFAULT_LH_RECLASS_CSV))
    parser.add_argument("--precision-json", default=str(DEFAULT_PRECISION_JSON))
    parser.add_argument("--precision-csv", default=str(DEFAULT_PRECISION_CSV))
    parser.add_argument("--canary-json", default=str(DEFAULT_CANARY_JSON))
    parser.add_argument("--canary-csv", default=str(DEFAULT_CANARY_CSV))
    parser.add_argument("--inventory-json", default=str(DEFAULT_INVENTORY_JSON))
    parser.add_argument("--evidence-jsonl", default=str(DEFAULT_EVIDENCE_JSONL))
    parser.add_argument("--draft-jsonl", default=str(DEFAULT_DRAFT_JSONL))
    parser.add_argument("--expected-source-rows", type=int, default=150)
    parser.add_argument("--output-csv", default="")
    parser.add_argument("--output-jsonl", default="")
    return parser.parse_args(argv)


def build_candidate_dataset(
    *,
    paths: CandidateInputPaths | None = None,
    expected_source_rows: int | None = 150,
) -> dict[str, Any]:
    paths = (paths or CandidateInputPaths()).resolved()
    blockers: list[str] = []
    validate_required_paths(paths, blockers)
    if blockers:
        raise FailClosedInputError(blockers)

    source_jsons = read_source_jsons(paths, blockers)
    for label, payload in source_jsons.items():
        validate_source_guardrails(label, payload, blockers)
    if blockers:
        raise FailClosedInputError(blockers)

    synthetic_rows = read_csv(paths.synthetic_csv)
    if expected_source_rows is not None and len(synthetic_rows) != expected_source_rows:
        blockers.append(f"synthetic diagnostic row count mismatch: expected {expected_source_rows}, got {len(synthetic_rows)}")

    quality_by_id = read_csv_by_id(paths.answer_quality_csv, "answer quality CSV", blockers)
    abstain_by_id = read_csv_by_id(paths.abstain_csv, "abstain breakdown CSV", blockers)
    false_positive_by_id = read_csv_by_id(paths.false_positive_csv, "false-positive CSV", blockers)
    lh_reclass_by_id = read_csv_by_id(paths.lh_reclassification_csv, "LH reclassification CSV", blockers)
    precision_by_id = read_csv_by_id(paths.precision_csv, "precision audit CSV", blockers)
    canary_by_id = read_csv_by_id(paths.canary_csv, "canary readiness CSV", blockers)
    evidence_by_id = read_jsonl_by_id(paths.evidence_jsonl, "answer evidence JSONL", blockers)
    draft_by_id = read_jsonl_by_id(paths.draft_jsonl, "deterministic draft JSONL", blockers)
    if blockers:
        raise FailClosedInputError(blockers)

    duplicate_query_ids = duplicate_values(str(row.get("query_id") or "") for row in synthetic_rows)
    if duplicate_query_ids:
        blockers.append(f"duplicate synthetic query_id values: {duplicate_query_ids[:5]}")
        raise FailClosedInputError(blockers)

    rows = [
        build_candidate_row(
            synthetic=row,
            quality=quality_by_id.get(str(row.get("query_id") or ""), {}),
            abstain=abstain_by_id.get(str(row.get("query_id") or ""), {}),
            false_positive=false_positive_by_id.get(str(row.get("query_id") or ""), {}),
            lh_reclass=lh_reclass_by_id.get(str(row.get("query_id") or ""), {}),
            precision=precision_by_id.get(str(row.get("query_id") or ""), {}),
            canary=canary_by_id.get(str(row.get("query_id") or ""), {}),
            evidence=evidence_by_id.get(str(row.get("query_id") or ""), {}),
            draft=draft_by_id.get(str(row.get("query_id") or ""), {}),
        )
        for row in synthetic_rows
    ]
    lane_counts = sorted_counter(Counter(str(row["review_lane"]) for row in rows))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "PASS",
        **OUTPUT_GUARDRAILS,
        "analysis_role": "diagnostic_gold_review_candidate_layer_only",
        "source_candidate_row_count": len(rows),
        "expected_source_rows": expected_source_rows,
        "review_lane_enum": REVIEW_LANES,
        "review_lane_counts": lane_counts,
        "duplicate_query_id_count": 0,
        "row_column_value_semantics_claimed": False,
        "table_semantics_success_claimed": False,
        "input_artifacts": [artifact_identity(path) for path in paths.as_dict().values()],
        "notes": [
            "Review lanes are diagnostic suggestions for human review only.",
            "Ambiguous rows are conservatively routed to lower-trust lanes.",
            "Table-like rows do not claim row/column/value or table semantics success.",
        ],
    }
    return {"summary": summary, "rows": rows}


def validate_required_paths(paths: CandidateInputPaths, blockers: list[str]) -> None:
    for label, path in paths.as_dict().items():
        if not path.exists():
            blockers.append(f"{label} missing: {display_path(path)}")


def read_source_jsons(paths: CandidateInputPaths, blockers: list[str]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for label, path in {
        "answer_quality": paths.answer_quality_json,
        "abstain_breakdown": paths.abstain_json,
        "false_positive_classification": paths.false_positive_json,
        "lh_reclassification": paths.lh_reclassification_json,
        "precision_audit": paths.precision_json,
        "canary_readiness": paths.canary_json,
        "inventory": paths.inventory_json,
    }.items():
        try:
            payloads[label] = read_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            blockers.append(f"{label} JSON read failed: {display_path(path)}: {exc}")
    return payloads


def validate_source_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    for key, expected in CORE_GUARDRAIL_VALUES.items():
        if key not in payload:
            blockers.append(f"{label} missing guardrail key: {key}")
            continue
        if payload.get(key) != expected:
            blockers.append(f"{label} guardrail {key} expected {expected!r}, got {payload.get(key)!r}")
    for key in ("local_llm_run", "actual_llm_answer_generation_run", "actual_generated_answer_output"):
        if key in payload and payload.get(key) is not False:
            blockers.append(f"{label} guardrail {key} expected False, got {payload.get(key)!r}")
    if payload.get("table_semantics_success_claimed") is True:
        blockers.append(f"{label} claims table_semantics_success_claimed=true")
    if payload.get("table_semantics_success_not_claimed") is not True and "table_semantics_success_claimed" not in payload:
        blockers.append(f"{label} must explicitly avoid table semantics success claims")
    row_column_claim = payload.get("row_column_value_semantics_claimed")
    readiness_policy = payload.get("readiness_policy") if isinstance(payload.get("readiness_policy"), Mapping) else {}
    if row_column_claim is True or readiness_policy.get("row_column_value_semantics_claimed") is True:
        blockers.append(f"{label} claims row_column_value_semantics_claimed=true")


def read_csv_by_id(path: Path, label: str, blockers: list[str]) -> dict[str, dict[str, str]]:
    try:
        rows = read_csv(path)
    except OSError as exc:
        blockers.append(f"{label} read failed: {display_path(path)}: {exc}")
        return {}
    return {str(row.get("query_id") or ""): row for row in rows if str(row.get("query_id") or "")}


def read_jsonl_by_id(path: Path, label: str, blockers: list[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    try:
        for row in iter_jsonl(path):
            query_id = str(row.get("query_id") or "")
            if query_id:
                rows[query_id] = row
    except (OSError, json.JSONDecodeError) as exc:
        blockers.append(f"{label} read failed: {display_path(path)}: {exc}")
    return rows


def build_candidate_row(
    *,
    synthetic: Mapping[str, Any],
    quality: Mapping[str, Any],
    abstain: Mapping[str, Any],
    false_positive: Mapping[str, Any],
    lh_reclass: Mapping[str, Any],
    precision: Mapping[str, Any],
    canary: Mapping[str, Any],
    evidence: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> dict[str, Any]:
    lane, reason, risk_tags = assign_review_lane(
        synthetic=synthetic,
        quality=quality,
        abstain=abstain,
        false_positive=false_positive,
        lh_reclass=lh_reclass,
        precision=precision,
        canary=canary,
        evidence=evidence,
        draft=draft,
    )
    suggestions = suggestions_for_lane(lane)
    page_no = first_text(
        evidence.get("citation", {}).get("page_no") if isinstance(evidence.get("citation"), Mapping) else None,
        quality.get("page_no"),
        synthetic.get("parser_derived_page_no"),
    )
    section_path = first_text(
        evidence.get("section_title"),
        lh_reclass.get("section_context"),
        synthetic.get("parser_derived_section_title"),
    )
    row = {
        "track": "PDF_SUPPLEMENTAL_ELEC_LH",
        "query_id": first_text(synthetic.get("query_id")),
        "dataset": first_text(synthetic.get("dataset_source"), evidence.get("dataset_source"), quality.get("dataset_source")),
        "source_file_name": first_text(synthetic.get("file_name"), evidence.get("file_name"), quality.get("file_name")),
        "page_no": page_no,
        "page_label": f"p{page_no}" if page_no else "",
        "section_path": section_path,
        "query": first_text(synthetic.get("query"), evidence.get("query")),
        "expected_evidence_excerpt": short_text(first_text(synthetic.get("anchor_text"), evidence.get("evidence_text_excerpt")), 500),
        "evidence_object_summary": evidence_summary(evidence=evidence, quality=quality, precision=precision, false_positive=false_positive),
        "deterministic_draft": deterministic_summary(draft),
        "review_lane": lane,
        **suggestions,
        "risk_tags": risk_tags,
        "diagnostic_reason": reason,
        **OUTPUT_GUARDRAILS,
        "source_join_signals": {
            "quality_reason": quality.get("reason"),
            "primary_abstain_reason": abstain.get("primary_abstain_reason"),
            "false_positive_classification": first_text(false_positive.get("classification"), lh_reclass.get("false_positive_classification")),
            "candidate_quality": precision.get("candidate_quality"),
            "canary_lane": canary.get("canary_lane"),
        },
    }
    return row


def assign_review_lane(
    *,
    synthetic: Mapping[str, Any],
    quality: Mapping[str, Any],
    abstain: Mapping[str, Any],
    false_positive: Mapping[str, Any],
    lh_reclass: Mapping[str, Any],
    precision: Mapping[str, Any],
    canary: Mapping[str, Any],
    evidence: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> tuple[str, str, list[str]]:
    risk_tags: list[str] = []
    classification = first_text(false_positive.get("classification"), lh_reclass.get("false_positive_classification"), precision.get("false_positive_classification"))
    candidate_quality = first_text(precision.get("candidate_quality"))
    canary_lane = first_text(canary.get("canary_lane"))
    primary_abstain = first_text(abstain.get("primary_abstain_reason"), draft.get("abstain_reason"))
    quality_reason = first_text(quality.get("reason"))
    anchor_type = first_text(synthetic.get("anchor_type"), evidence.get("anchor_type"), quality.get("anchor_type"))
    evidence_ready = truthy(quality.get("evidence_ready")) or bool(first_text(draft.get("answer_draft")))
    table_like = truthy(quality.get("table_like_context_candidate")) or truthy(evidence.get("table_like_context_candidate"))
    ocr_needed = truthy(quality.get("ocr_needed_candidate")) or truthy(evidence.get("ocr_needed_object")) or truthy(evidence.get("ocr_needed_candidate"))
    answer_draft = first_text(draft.get("answer_draft"))

    add_tag(risk_tags, classification)
    add_tag(risk_tags, candidate_quality)
    add_tag(risk_tags, canary_lane)
    add_tag(risk_tags, primary_abstain)
    if table_like:
        risk_tags.append("table_like_context_candidate_only")
    if truthy(quality.get("keyword_only_risk")) or truthy(evidence.get("keyword_only_risk")):
        risk_tags.append("keyword_only_risk")
    if ocr_needed:
        risk_tags.append("ocr_needed_candidate")

    if ocr_needed:
        return (
            "OCR_NEEDED_UNSUPPORTED",
            "OCR-needed source remains diagnostic-only and is deferred from official gold candidacy.",
            unique(risk_tags),
        )
    if candidate_quality == "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE":
        return (
            "HIGH_CONFIDENCE_TABLE_CANDIDATE",
            "Precision audit marked a high-confidence table evidence candidate, but table semantics success remains unclaimed.",
            unique(risk_tags),
        )
    if canary_lane == "RESTRICTED_TABLE_CONTEXT_CANARY_READY":
        return (
            "READY_RESTRICTED_TABLE_CONTEXT",
            "Restricted table-context wording is reviewable as extractive context only, without row/column/value finalization.",
            unique(risk_tags),
        )
    if canary_lane == "SAFE_SECTION_SUMMARY_CANARY_READY":
        return (
            "READY_SECTION_SUMMARY",
            "Deterministic section-summary draft has content-bearing evidence and is ready for human review.",
            unique(risk_tags),
        )
    if classification == "REFERENCE_CODE_FRAGMENT" and evidence_ready and answer_draft and not primary_abstain:
        return (
            "READY_EXTRACTIVE_CONTEXT",
            "Reference-code risk is preserved as a tag, but the row has content-bearing extractive context for human review.",
            unique(risk_tags),
        )
    if classification == "REFERENCE_CODE_FRAGMENT" or lh_reclass.get("revised_fix_lane") == "REFERENCE_CODE_FRAGMENT_FILTER_REQUIRED":
        return (
            "FALSE_POSITIVE_REFERENCE_CODE",
            "Reference-code or follows-clause fragment is included only as a diagnostic control.",
            unique(risk_tags),
        )
    if classification == "BULLET_OR_FORMULA_CONTEXT":
        return (
            "FALSE_POSITIVE_BULLET_OR_FORMULA",
            "Bullet/formula context is not a row/column/value table semantics success claim.",
            unique(risk_tags),
        )
    if classification in {"FOOTER_OR_PRINT_ARTIFACT", "SECTION_OR_LIST_FRAGMENT", "NOT_TABLE_LIKE_AFTER_REVIEW"}:
        return (
            "FALSE_POSITIVE_NOISE",
            "False-positive/noise classification keeps this row in sampled control review only.",
            unique(risk_tags),
        )
    if primary_abstain == "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE":
        return (
            "ABSTAIN_TABLE_LIKE_NO_ROW_COLUMN_VALUE",
            "Table-like context lacks supported row/column/value semantics and stays abstain control.",
            unique(risk_tags),
        )
    if primary_abstain in {"ONLY_KEYWORD_OR_LABEL_PRESENT", "SYNTHETIC_QUERY_TOO_BROAD"} or quality_reason == "keyword_only_without_sufficient_context":
        return (
            "ABSTAIN_KEYWORD_OR_LABEL_ONLY",
            "Keyword or label-only evidence is too weak for a positive gold decision without user review.",
            unique(risk_tags),
        )
    if primary_abstain in {"SECTION_CONTEXT_TOO_GENERIC", "NEARBY_CONTEXT_NOT_ANSWER_SUPPORTING"}:
        return (
            "ABSTAIN_GENERIC_SECTION_CONTEXT",
            "Generic section context is included as a low-trust diagnostic control.",
            unique(risk_tags),
        )
    if evidence_ready and answer_draft and not table_like:
        if anchor_type in {"paragraph_candidate", "semantic_anchor_candidate"}:
            return (
                "READY_SECTION_SUMMARY",
                "Content-bearing paragraph/semantic context has a deterministic section-summary draft.",
                unique(risk_tags),
            )
        return (
            "READY_EXTRACTIVE_CONTEXT",
            "Content-bearing extractive context has a deterministic draft for human review.",
            unique(risk_tags),
        )
    if evidence_ready and answer_draft and table_like:
        return (
            "READY_RESTRICTED_TABLE_CONTEXT",
            "Table-like evidence is reviewable only as restricted extractive context.",
            unique(risk_tags),
        )
    return (
        "POLICY_OR_DIAGNOSTIC_ONLY",
        "Ambiguous diagnostic row was conservatively routed to policy/user-review-only status.",
        unique(risk_tags),
    )


def suggestions_for_lane(lane: str) -> dict[str, str]:
    if lane in {"READY_SECTION_SUMMARY", "READY_EXTRACTIVE_CONTEXT"}:
        return {
            "suggested_gold_decision": "USER_REVIEW_REQUIRED_POSSIBLE_INCLUDE",
            "suggested_answerability_label": "candidate_answerable_requires_user_review",
            "suggested_relevance_label": "candidate_relevant_requires_user_review",
            "suggested_expected_evidence_policy": "extractive_excerpt_candidate",
            "suggested_denominator_policy": "no_official_change_user_must_decide",
        }
    if lane == "READY_RESTRICTED_TABLE_CONTEXT":
        return {
            "suggested_gold_decision": "USER_REVIEW_REQUIRED_RESTRICTED_TABLE_CONTEXT",
            "suggested_answerability_label": "candidate_answerable_context_only_requires_user_review",
            "suggested_relevance_label": "candidate_relevant_context_only_requires_user_review",
            "suggested_expected_evidence_policy": "restricted_table_context_only_no_row_column_value",
            "suggested_denominator_policy": "no_official_change_user_must_decide",
        }
    if lane == "HIGH_CONFIDENCE_TABLE_CANDIDATE":
        return {
            "suggested_gold_decision": "USER_REVIEW_REQUIRED_TABLE_EVIDENCE_CANDIDATE",
            "suggested_answerability_label": "candidate_answerable_table_evidence_requires_user_review",
            "suggested_relevance_label": "candidate_relevant_table_evidence_requires_user_review",
            "suggested_expected_evidence_policy": "table_evidence_candidate_only_no_semantics_success",
            "suggested_denominator_policy": "no_official_change_user_must_decide",
        }
    if lane == "OCR_NEEDED_UNSUPPORTED":
        return {
            "suggested_gold_decision": "HOLD_FOR_SEPARATE_OCR_POLICY",
            "suggested_answerability_label": "ocr_answerability_deferred",
            "suggested_relevance_label": "ocr_relevance_deferred",
            "suggested_expected_evidence_policy": "ocr_policy_deferred",
            "suggested_denominator_policy": "no_official_change_user_must_decide",
        }
    if lane.startswith("ABSTAIN_") or lane.startswith("FALSE_POSITIVE_"):
        return {
            "suggested_gold_decision": "CONTROL_REVIEW_RECOMMENDED_EXCLUDE",
            "suggested_answerability_label": "suggested_unanswerable_control",
            "suggested_relevance_label": "suggested_not_relevant_or_insufficient_control",
            "suggested_expected_evidence_policy": "exclude_as_control_unless_user_overrides",
            "suggested_denominator_policy": "no_official_change_user_must_decide",
        }
    return {
        "suggested_gold_decision": "USER_POLICY_DECISION_REQUIRED_DIAGNOSTIC_ONLY",
        "suggested_answerability_label": "policy_pending",
        "suggested_relevance_label": "policy_pending",
        "suggested_expected_evidence_policy": "policy_pending",
        "suggested_denominator_policy": "no_official_change_user_must_decide",
    }


def evidence_summary(
    *,
    evidence: Mapping[str, Any],
    quality: Mapping[str, Any],
    precision: Mapping[str, Any],
    false_positive: Mapping[str, Any],
) -> str:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    parts = [
        f"evidence={short_text(first_text(evidence.get('evidence_text_excerpt'), evidence.get('paragraph_summary')), 260)}",
        f"nearby={short_text(first_text(evidence.get('nearby_context')), 220)}",
        f"quality_reason={first_text(quality.get('reason'))}",
        f"candidate_quality={first_text(precision.get('candidate_quality'))}",
        f"false_positive={first_text(false_positive.get('classification'))}",
    ]
    if citation:
        parts.append(
            "citation="
            + json.dumps(
                {
                    "page_no": citation.get("page_no"),
                    "bbox_present": bool(first_text(citation.get("bbox"))),
                    "bbox_contract_success_not_claimed": True,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return short_text(" | ".join(part for part in parts if part and not part.endswith("=")), 900)


def deterministic_summary(draft: Mapping[str, Any]) -> str:
    answer = first_text(draft.get("answer_draft"))
    if answer:
        return short_text(answer, 700)
    reason = first_text(draft.get("abstain_reason"))
    if reason:
        return f"ABSTAIN: {reason}"
    return ""


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value).strip()
        if text:
            return text
    return ""


def add_tag(tags: list[str], value: str) -> None:
    if value:
        tags.append(value)


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def duplicate_values(values: Iterable[str]) -> list[str]:
    counter = Counter(value for value in values if value)
    return [value for value, count in counter.items() if count > 1]


if __name__ == "__main__":
    raise SystemExit(main())
