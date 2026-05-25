"""Deterministic citation verifier for query-time RAG evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.capabilities.rag_orchestrator.evidence import (
    EMBEDDING_STATUS_EMBEDDED,
    RETRIEVAL_BACKEND_VECTOR,
    SOURCE_FILE_TYPE_PDF,
    SOURCE_FILE_TYPE_SPREADSHEET,
    Evidence,
    QueryPolicy,
)

FATAL_RETRIEVAL_BACKEND = "retrieval_backend_not_vector"
FATAL_INDEX_VERSION = "index_version_mismatch"
FATAL_EMBEDDING_STATUS = "embedding_status_not_embedded"
FATAL_MISSING_CITATION = "missing_citation_text"
FATAL_MISSING_LOCATION = "missing_location_json"
FATAL_INVALID_LOCATION = "invalid_location_json"
FATAL_SOURCE_TYPE = "source_file_type_mismatch"
FATAL_PARSER_VERSION = "parser_version_not_allowed"
FATAL_TENANT = "tenant_id_mismatch"
FATAL_ACL = "acl_tags_not_allowed"
FATAL_PDF_PAGE = "pdf_locator_missing_page"
FATAL_PDF_STABLE_IDENTITY_REQUIRED = "stable_identity_required"
FATAL_XLSX_SHEET = "xlsx_locator_missing_sheet"
FATAL_XLSX_RANGE = "xlsx_locator_missing_range"
FATAL_XLSX_HIDDEN_NEGATIVE_OR_EXCLUDED_ROW = "hidden_negative_or_excluded_row_guard"

WARNING_OCR_LOWER_TRUST = "ocr_lower_trust"
WARNING_BBOX_CONFIDENCE_LOW = "bbox_confidence_low"
WARNING_TABLE_TRUNCATED = "table_truncated"

_A1_RANGE_RE = re.compile(
    r"^\$?[A-Za-z]{1,3}\$?[1-9][0-9]*"
    r"(?::\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)?$"
)


@dataclass(frozen=True)
class EvidenceVerification:
    evidence: Evidence
    status: str
    fatal_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def evidence_id(self) -> str:
        return self.evidence.evidence_id

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def to_dict(self) -> dict[str, Any]:
        evidence_body = self.evidence.to_dict()
        evidence_body["verification"] = {
            "status": self.status,
            "reasons": list(self.fatal_reasons),
            "warnings": list(self.warnings),
        }
        return {
            "evidenceId": self.evidence_id,
            "status": self.status,
            "fatalReasons": list(self.fatal_reasons),
            "warnings": list(self.warnings),
            "evidence": evidence_body,
        }


@dataclass(frozen=True)
class CitationVerificationResult:
    verified: tuple[EvidenceVerification, ...]
    rejected: tuple[EvidenceVerification, ...]

    @property
    def metrics(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "verified_count": len(self.verified),
            "rejected_count": len(self.rejected),
            "warning_count": sum(len(item.warnings) for item in self.verified),
        }
        for item in self.rejected:
            for reason in item.fatal_reasons:
                counts[f"{reason}_count"] = counts.get(f"{reason}_count", 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": [item.to_dict() for item in self.verified],
            "rejected": [item.to_dict() for item in self.rejected],
            "metrics": self.metrics,
        }


def citation_verify_tool(
    evidence: Iterable[Evidence],
    policy: QueryPolicy,
) -> CitationVerificationResult:
    """Verify evidence without LLM judgment."""

    verified: list[EvidenceVerification] = []
    rejected: list[EvidenceVerification] = []

    for item in evidence:
        fatal_reasons = _fatal_reasons(item, policy)
        warnings = _warnings(item)
        status = "rejected" if fatal_reasons else "verified"
        verification = EvidenceVerification(
            evidence=item,
            status=status,
            fatal_reasons=tuple(fatal_reasons),
            warnings=tuple(warnings),
        )
        if fatal_reasons:
            rejected.append(verification)
        else:
            verified.append(verification)

    return CitationVerificationResult(
        verified=tuple(verified),
        rejected=tuple(rejected),
    )


def verify_evidence(
    evidence: Iterable[Evidence],
    policy: QueryPolicy,
) -> CitationVerificationResult:
    return citation_verify_tool(evidence, policy)


def _fatal_reasons(evidence: Evidence, policy: QueryPolicy) -> list[str]:
    reasons: list[str] = []
    source_type = evidence.source_file_type.upper()

    if evidence.retrieval_backend != RETRIEVAL_BACKEND_VECTOR:
        reasons.append(FATAL_RETRIEVAL_BACKEND)
    if evidence.index_version != policy.required_index_version:
        reasons.append(FATAL_INDEX_VERSION)
    if (
        evidence.embedding_status != EMBEDDING_STATUS_EMBEDDED
        or evidence.embedding_status != policy.required_embedding_status
    ):
        reasons.append(FATAL_EMBEDDING_STATUS)
    if not evidence.citation_text:
        reasons.append(FATAL_MISSING_CITATION)
    if not evidence.location_json:
        reasons.append(FATAL_MISSING_LOCATION)
    if source_type not in policy.allowed_source_file_types:
        reasons.append(FATAL_SOURCE_TYPE)
    if evidence.parser_version not in policy.allowed_parser_versions:
        reasons.append(FATAL_PARSER_VERSION)
    if policy.tenant_id and evidence.tenant_id != policy.tenant_id:
        reasons.append(FATAL_TENANT)
    if policy.acl_tags and not (set(policy.acl_tags) & set(evidence.acl_tags)):
        reasons.append(FATAL_ACL)
    if source_type == SOURCE_FILE_TYPE_PDF and _is_pdf_file_identity_evidence(evidence):
        if not _has_stable_pdf_document_identity(evidence):
            reasons.append(FATAL_PDF_STABLE_IDENTITY_REQUIRED)
    if _is_spreadsheet_source_type(source_type) and _is_xlsx_hidden_or_excluded(evidence):
        reasons.append(FATAL_XLSX_HIDDEN_NEGATIVE_OR_EXCLUDED_ROW)

    location = evidence.location_json
    if location and not isinstance(location, Mapping):
        reasons.append(FATAL_INVALID_LOCATION)
        return reasons

    if source_type == SOURCE_FILE_TYPE_PDF and location:
        if not _has_valid_pdf_page_locator(location):
            reasons.append(FATAL_PDF_PAGE)
    if _is_spreadsheet_source_type(source_type) and location:
        if not _has_any(location, ("sheet_name", "sheetName")):
            reasons.append(FATAL_XLSX_SHEET)
        if not _has_valid_xlsx_table_locator(location):
            reasons.append(FATAL_XLSX_RANGE)

    return reasons


def _warnings(evidence: Evidence) -> list[str]:
    warnings: list[str] = []
    location = evidence.location_json if isinstance(evidence.location_json, Mapping) else {}
    extra = evidence.extra

    if bool(_get_any(location, ("ocr_used", "ocrUsed"))) or bool(
        _get_any(extra, ("ocr_lower_trust", "ocrLowerTrust"))
    ):
        warnings.append(WARNING_OCR_LOWER_TRUST)

    bbox_confidence = _get_any(
        location,
        ("bbox_confidence", "bboxConfidence", "ocr_confidence", "ocrConfidence"),
    )
    if _is_low_confidence(bbox_confidence):
        warnings.append(WARNING_BBOX_CONFIDENCE_LOW)

    if bool(_get_any(location, ("table_truncated", "tableTruncated", "truncated"))) or bool(
        _get_any(extra, ("table_truncated", "tableTruncated", "truncated"))
    ):
        warnings.append(WARNING_TABLE_TRUNCATED)

    return warnings


def _has_any(data: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(_get_any(data, (key,)) not in (None, "") for key in keys)


def _get_any(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _has_valid_pdf_page_locator(location: Mapping[str, Any]) -> bool:
    one_based = _get_any(location, ("page", "page_no", "pageNo", "page_start", "pageStart"))
    if one_based not in (None, ""):
        return _is_int_at_least(one_based, minimum=1)

    zero_based = _get_any(location, ("physical_page_index", "physicalPageIndex"))
    if zero_based not in (None, ""):
        return _is_int_at_least(zero_based, minimum=0)

    return False


def _has_valid_xlsx_table_locator(location: Mapping[str, Any]) -> bool:
    table_id = _get_any(location, ("table_id", "tableId"))
    if isinstance(table_id, str) and table_id.strip():
        return True

    cell_range = _get_any(location, ("cell_range", "cellRange", "range", "usedRange"))
    if not isinstance(cell_range, str):
        return False
    return bool(_A1_RANGE_RE.fullmatch(cell_range.strip()))


def _is_spreadsheet_source_type(source_type: str) -> bool:
    return source_type in {SOURCE_FILE_TYPE_SPREADSHEET, "XLSX", "XLSM"}


def _is_pdf_file_identity_evidence(evidence: Evidence) -> bool:
    lane = _metadata_text(
        evidence,
        (
            "requestedEvidenceLane",
            "requested_evidence_lane",
            "evidenceLane",
            "evidence_lane",
            "retrievalLane",
            "retrieval_lane",
            "targetLane",
            "target_lane",
        ),
    )
    normalized = lane.lower()
    return normalized in {
        "pdf_file",
        "pdf_file_lookup",
        "pdf_file_document_identity",
        "file_document_identity",
        "file_identity",
    }


def _has_stable_pdf_document_identity(evidence: Evidence) -> bool:
    if _metadata_bool(
        evidence,
        (
            "genericFilenameIdentity",
            "generic_filename_identity",
            "filenameOnlyIdentity",
            "filename_only_identity",
        ),
    ):
        return False
    return _metadata_bool(
        evidence,
        (
            "stableDocumentIdentity",
            "stable_document_identity",
            "stableIdentity",
            "stable_identity",
        ),
    )


def _is_xlsx_hidden_or_excluded(evidence: Evidence) -> bool:
    if _metadata_bool(
        evidence,
        (
            "hidden",
            "hiddenSheet",
            "hidden_sheet",
            "hiddenRow",
            "hidden_row",
            "hiddenColumn",
            "hidden_column",
            "hiddenNegative",
            "hidden_negative",
            "excluded",
            "excludedRow",
            "excluded_row",
        ),
    ):
        return True

    policy_guard = _metadata_text(evidence, ("policyGuard", "policy_guard"))
    if policy_guard == FATAL_XLSX_HIDDEN_NEGATIVE_OR_EXCLUDED_ROW:
        return True

    policy_label = _metadata_text(evidence, ("policyLabel", "policy_label")).lower()
    review_status = _metadata_text(evidence, ("reviewStatus", "review_status")).lower()
    return "hidden" in policy_label or "excluded" in review_status


def _metadata_text(evidence: Evidence, keys: tuple[str, ...]) -> str:
    value = _metadata_value(evidence, keys)
    return "" if value in (None, "") else str(value).strip()


def _metadata_bool(evidence: Evidence, keys: tuple[str, ...]) -> bool:
    value = _metadata_value(evidence, keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _metadata_value(evidence: Evidence, keys: tuple[str, ...]) -> Any:
    for source in _metadata_sources(evidence):
        value = _get_any(source, keys)
        if value not in (None, ""):
            return value
    return None


def _metadata_sources(evidence: Evidence) -> tuple[Mapping[str, Any], ...]:
    sources: list[Mapping[str, Any]] = []
    if isinstance(evidence.location_json, Mapping):
        sources.append(evidence.location_json)
    if isinstance(evidence.extra, Mapping):
        sources.append(evidence.extra)
        retriever_metadata = evidence.extra.get("retriever_metadata")
        if isinstance(retriever_metadata, Mapping):
            sources.append(retriever_metadata)
    return tuple(sources)


def _is_int_at_least(value: Any, *, minimum: int) -> bool:
    if isinstance(value, bool):
        return False
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return parsed >= minimum and str(value).strip() == str(parsed)


def _is_low_confidence(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        return float(value) < 0.5
    except (TypeError, ValueError):
        return False
