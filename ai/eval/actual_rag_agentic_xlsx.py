from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ai.eval.actual_rag_dataset import DatasetSchemaError
from ai.eval.actual_rag_judging import normalize_answer_text


AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION = "actual_rag_eval.agentic_xlsx_query_anchor_taxonomy.v1"
AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION = (
    "actual_rag_eval.agentic_xlsx_protected_anchor_verifier.v1"
)
AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION = "actual_rag_eval.agentic_xlsx_axis_inspector.v1"
AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION = "actual_rag_eval.agentic_xlsx_repair_explainer.v1"
AGENTIC_XLSX_AXIS_REPAIR_DIAGNOSTIC_SCHEMA_VERSION = (
    "actual_rag_eval.agentic_xlsx_axis_repair_diagnostic.v1"
)
AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION = (
    "actual_rag_eval.agentic_xlsx_regated_candidate_simulator.v1"
)
AGENTIC_XLSX_COORDINATOR_SCHEMA_VERSION = "actual_rag_eval.agentic_xlsx_coordinator.v1"
AGENTIC_XLSX_ANCHOR_TAXONOMY_CATEGORIES = (
    "intent_token",
    "date_or_period",
    "route_or_line",
    "organization_or_facility",
    "measure_or_column",
    "numeric_or_unit",
    "entity",
    "unknown_protected",
)
AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES = (
    "intent_anchor_only",
    "query_anchor_and_axis_missing",
    "axis_materialization_gap",
    "candidate_budget_gap",
    "source_family_or_route_gap",
    "unsafe_classifier_removal",
    "unknown_fail_closed",
)
AGENTIC_XLSX_TOOL_SEQUENCE = (
    "QueryAnchorTaxonomyTool",
    "ProtectedAnchorVerifierTool",
    "XlsxAxisInspectorTool",
    "CandidateRepairExplainerTool",
    "RegatedCandidateSimulatorTool",
)


@dataclass(frozen=True)
class AgenticXlsxQueryAnchorTaxonomyRecord:
    token: str
    category: str
    is_removable_intent_token: bool
    is_protected_anchor: bool
    reason: str
    schema_version: str = AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION


@dataclass(frozen=True)
class AgenticXlsxProtectedAnchorVerifierRecord:
    proposed_removed_tokens: tuple[str, ...] = ()
    approved_removed_tokens: tuple[str, ...] = ()
    rejected_removed_tokens: tuple[str, ...] = ()
    protected_rejection_reasons: Mapping[str, str] = field(default_factory=dict)
    schema_version: str = AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION


@dataclass(frozen=True)
class AgenticXlsxAxisInspectionRecord:
    has_required_period_axis: bool
    has_required_entity_axis: bool
    has_required_measure_axis: bool
    has_display_value: bool
    missing_axes: tuple[str, ...] = ()
    source_owned_axis_evidence: Mapping[str, str] = field(default_factory=dict)
    schema_version: str = AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION


@dataclass(frozen=True)
class AgenticXlsxRepairExplanationRecord:
    primary_failure_family: str
    secondary_failure_families: tuple[str, ...]
    safe_to_simulate_intent_removal: bool
    repair_recommendation: str
    evidence_summary: str
    schema_version: str = AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION


@dataclass(frozen=True)
class AgenticXlsxRegatedCandidateSimulationRecord:
    original_rejection_reason: str
    simulated_rejection_reason: str
    approved_removed_tokens: tuple[str, ...]
    protected_tokens_preserved: tuple[str, ...]
    axis_status_after_simulation: Mapping[str, Any]
    would_be_accepted_by_existing_gate: bool
    report_only_diagnostic: bool = True
    official_metric: bool = False
    schema_version: str = AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION


@dataclass(frozen=True)
class AgenticXlsxCoordinatorRecord:
    tool_sequence: tuple[str, ...] = AGENTIC_XLSX_TOOL_SEQUENCE
    taxonomy_records: tuple[AgenticXlsxQueryAnchorTaxonomyRecord, ...] = ()
    anchor_verification: AgenticXlsxProtectedAnchorVerifierRecord | None = None
    axis_inspection: AgenticXlsxAxisInspectionRecord | None = None
    repair_explanation: AgenticXlsxRepairExplanationRecord | None = None
    regated_simulation: AgenticXlsxRegatedCandidateSimulationRecord | None = None
    fail_closed: bool = False
    report_only_diagnostic: bool = True
    official_metric: bool = False
    schema_version: str = AGENTIC_XLSX_COORDINATOR_SCHEMA_VERSION


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _agentic_xlsx_record_value(record: Any, field_name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(field_name)
    return getattr(record, field_name, None)


def _agentic_xlsx_clean_tuple(run_id: str, tool_name: str, field_name: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must be a list")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must contain strings")
        clean_item = _clean(item)
        if not clean_item:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must contain non-empty strings")
        cleaned.append(clean_item)
    return tuple(cleaned)


def _agentic_xlsx_bool(run_id: str, tool_name: str, field_name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must be boolean")
    return value


def _agentic_xlsx_required_string(run_id: str, tool_name: str, field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must be a string")
    clean_value = _clean(value)
    if not clean_value:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must be non-empty")
    return clean_value


def _looks_like_measure_anchor(anchor: str) -> bool:
    normalized = normalize_answer_text(anchor)
    if not normalized:
        return False
    measure_markers = (
        "amount",
        "count",
        "date",
        "address",
        "code",
        "total",
        "rate",
        "price",
        "value",
        "금액",
        "승객수",
        "총승객수",
        "주소",
        "상세주소",
        "지정일자",
        "설치신고일자",
        "코드",
        "합계",
        "평균",
        "비율",
        "수",
    )
    return any(marker in normalized for marker in measure_markers)


def _agentic_xlsx_query_anchor_category(token: str) -> tuple[str, str]:
    clean_token = _clean(token)
    normalized = normalize_answer_text(clean_token)
    compact = re.sub(r"\s+", "", clean_token)
    normalized_compact = re.sub(r"\s+", "", normalized)
    removable_intent_tokens = {
        normalize_answer_text(value)
        for value in (
            "무엇입니까",
            "명입니까",
            "지정된",
            "알려주세요",
            "구하시오",
        )
    }
    if normalized in removable_intent_tokens:
        return "intent_token", "narrow query-intent token approved for diagnostic removal"
    if re.fullmatch(r"\d{2,4}년(?:\d{1,2}월)?|\d{1,2}월|\d{1,2}일", compact):
        return "date_or_period", "date or period anchor must be preserved"
    if compact.endswith("호선") or compact.endswith("선") or normalized_compact in {"신논현"}:
        return "route_or_line", "route or line anchor must be preserved"
    if any(marker in compact for marker in ("요양원", "병원", "학교", "공사", "공단", "센터")):
        return "organization_or_facility", "organization or facility anchor must be preserved"
    measure_markers = (
        "population",
        "boarding",
        "alighting",
        "amount",
        "count",
        "rate",
        "ranking",
        "category",
        "score",
        "label",
        "인구",
        "승차",
        "하차",
        "승객수",
        "총승객수",
        "금액",
        "비율",
        "순위",
        "분류",
        "유형",
        "점수",
        "라벨",
        "상세주소",
        "주소",
        "기관별상세주소",
    )
    if _looks_like_measure_anchor(clean_token) or any(marker in normalized_compact for marker in measure_markers):
        return "measure_or_column", "measure or column anchor must be preserved"
    if (
        re.search(r"\d", clean_token)
        or "원달러" in normalized_compact
        or re.search(r"(?:명|건|원|달러|%|퍼센트|비율)$", compact)
    ):
        return "numeric_or_unit", "numeric or unit anchor must be preserved"
    return "unknown_protected", "unknown token is protected by default"


def validate_agentic_xlsx_query_anchor_taxonomy_output(run_id: str, records: Sequence[Any]) -> None:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        raise DatasetSchemaError(f"{run_id}: query_anchor_taxonomy output must be a list")
    seen_tokens: set[str] = set()
    for index, record in enumerate(records):
        tool_name = f"query_anchor_taxonomy[{index}]"
        if not isinstance(record, (AgenticXlsxQueryAnchorTaxonomyRecord, Mapping)):
            raise DatasetSchemaError(f"{run_id}: {tool_name} must be a taxonomy record")
        if _agentic_xlsx_record_value(record, "schema_version") != AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
        token = _agentic_xlsx_required_string(run_id, tool_name, "token", _agentic_xlsx_record_value(record, "token"))
        normalized_token = normalize_answer_text(token)
        if normalized_token in seen_tokens:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.token duplicate")
        seen_tokens.add(normalized_token)
        category = _agentic_xlsx_required_string(
            run_id,
            tool_name,
            "category",
            _agentic_xlsx_record_value(record, "category"),
        )
        if category not in AGENTIC_XLSX_ANCHOR_TAXONOMY_CATEGORIES:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.category unsupported")
        is_removable = _agentic_xlsx_bool(
            run_id,
            tool_name,
            "is_removable_intent_token",
            _agentic_xlsx_record_value(record, "is_removable_intent_token"),
        )
        is_protected = _agentic_xlsx_bool(
            run_id,
            tool_name,
            "is_protected_anchor",
            _agentic_xlsx_record_value(record, "is_protected_anchor"),
        )
        _agentic_xlsx_required_string(run_id, tool_name, "reason", _agentic_xlsx_record_value(record, "reason"))
        if category == "intent_token":
            if is_protected or not is_removable:
                raise DatasetSchemaError(
                    f"{run_id}: {tool_name}.intent_token must be removable and not protected"
                )
            continue
        if is_removable:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.is_removable_intent_token only intent_token may be True")
        if not is_protected:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.non-intent category must be protected")


def agentic_xlsx_query_anchor_taxonomy_tool(tokens: Sequence[str]) -> tuple[AgenticXlsxQueryAnchorTaxonomyRecord, ...]:
    clean_tokens = _agentic_xlsx_clean_tuple("agentic_xlsx", "query_anchor_taxonomy", "tokens", tokens)
    records: list[AgenticXlsxQueryAnchorTaxonomyRecord] = []
    for clean_token in clean_tokens:
        category, reason = _agentic_xlsx_query_anchor_category(clean_token)
        is_intent = category == "intent_token"
        records.append(
            AgenticXlsxQueryAnchorTaxonomyRecord(
                token=clean_token,
                category=category,
                is_removable_intent_token=is_intent,
                is_protected_anchor=not is_intent,
                reason=reason,
            )
        )
    result = tuple(records)
    validate_agentic_xlsx_query_anchor_taxonomy_output("agentic_xlsx", result)
    return result


def validate_agentic_xlsx_protected_anchor_verifier_output(
    run_id: str,
    verification: AgenticXlsxProtectedAnchorVerifierRecord | Mapping[str, Any],
    *,
    taxonomy_records: Sequence[AgenticXlsxQueryAnchorTaxonomyRecord | Mapping[str, Any]] = (),
) -> None:
    tool_name = "protected_anchor_verifier"
    if not isinstance(verification, (AgenticXlsxProtectedAnchorVerifierRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be a verifier record")
    if _agentic_xlsx_record_value(verification, "schema_version") != AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    proposed = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "proposed_removed_tokens",
        _agentic_xlsx_record_value(verification, "proposed_removed_tokens"),
    )
    approved = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "approved_removed_tokens",
        _agentic_xlsx_record_value(verification, "approved_removed_tokens"),
    )
    rejected = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "rejected_removed_tokens",
        _agentic_xlsx_record_value(verification, "rejected_removed_tokens"),
    )
    if set(approved) & set(rejected):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens overlap rejected_removed_tokens")
    if not set(approved).issubset(set(proposed)) or not set(rejected).issubset(set(proposed)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} outputs must be proposed tokens")
    if set(approved) | set(rejected) != set(proposed):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must classify every proposed token")
    reasons = _agentic_xlsx_record_value(verification, "protected_rejection_reasons")
    if not isinstance(reasons, Mapping):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.protected_rejection_reasons must be present")
    for token in rejected:
        if not isinstance(reasons.get(token), str) or not _clean(reasons.get(token)):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.protected_rejection_reasons.{token} must be non-empty")
    if not taxonomy_records:
        if approved:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens missing taxonomy")
        if proposed and set(rejected) != set(proposed):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.without taxonomy must reject every proposed token")
    if taxonomy_records:
        validate_agentic_xlsx_query_anchor_taxonomy_output(run_id, taxonomy_records)
        taxonomy_by_token = {
            _clean(_agentic_xlsx_record_value(record, "token")): record
            for record in taxonomy_records
        }
        for token in approved:
            record = taxonomy_by_token.get(token)
            if record is None:
                raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens missing taxonomy")
            if _clean(_agentic_xlsx_record_value(record, "category")) != "intent_token":
                raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens contains protected anchor")
            if _agentic_xlsx_record_value(record, "is_removable_intent_token") is not True:
                raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens must be removable")
        for token in proposed:
            record = taxonomy_by_token.get(token)
            if record is None:
                if token not in rejected:
                    raise DatasetSchemaError(f"{run_id}: {tool_name}.unknown token must be rejected")
                continue
            category = _clean(_agentic_xlsx_record_value(record, "category"))
            is_protected = _agentic_xlsx_record_value(record, "is_protected_anchor") is True
            if (category != "intent_token" or is_protected) and token not in rejected:
                raise DatasetSchemaError(f"{run_id}: {tool_name}.protected anchor must be rejected")


def agentic_xlsx_protected_anchor_verifier_tool(
    *,
    proposed_removed_tokens: Sequence[str],
    taxonomy_records: Sequence[AgenticXlsxQueryAnchorTaxonomyRecord | Mapping[str, Any]],
) -> AgenticXlsxProtectedAnchorVerifierRecord:
    validate_agentic_xlsx_query_anchor_taxonomy_output("agentic_xlsx", taxonomy_records)
    proposed_tokens = _agentic_xlsx_clean_tuple(
        "agentic_xlsx",
        "protected_anchor_verifier",
        "proposed_removed_tokens",
        proposed_removed_tokens,
    )
    taxonomy_by_token = {
        _clean(_agentic_xlsx_record_value(record, "token")): record
        for record in taxonomy_records
    }
    approved: list[str] = []
    rejected: list[str] = []
    rejection_reasons: dict[str, str] = {}
    for token in proposed_tokens:
        record = taxonomy_by_token.get(token)
        if record is not None and _clean(_agentic_xlsx_record_value(record, "category")) == "intent_token":
            approved.append(token)
            continue
        rejected.append(token)
        if record is None:
            rejection_reasons[token] = "token has no taxonomy record and is protected by default"
        else:
            rejection_reasons[token] = _clean(_agentic_xlsx_record_value(record, "reason")) or (
                "protected anchor cannot be removed"
            )
    verification = AgenticXlsxProtectedAnchorVerifierRecord(
        proposed_removed_tokens=proposed_tokens,
        approved_removed_tokens=tuple(approved),
        rejected_removed_tokens=tuple(rejected),
        protected_rejection_reasons=rejection_reasons,
    )
    validate_agentic_xlsx_protected_anchor_verifier_output(
        "agentic_xlsx",
        verification,
        taxonomy_records=taxonomy_records,
    )
    return verification
