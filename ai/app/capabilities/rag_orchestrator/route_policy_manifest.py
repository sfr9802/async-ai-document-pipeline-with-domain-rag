"""Versioned diagnostic route-policy manifest loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


ROUTE_POLICY_MANIFEST_SCHEMA_VERSION = "rag_route_policy_manifest_v1"
DEFAULT_ROUTE_POLICY_MANIFEST_PATH = Path(__file__).with_name("route_policy_manifest.json")
EXPECTED_ROUTE_POLICY_QUERY_ID_COUNTS = {
    "xlsx_pending_evidence_query_ids": 2,
    "pdf_policy_excluded_query_ids": 6,
    "pdf_stable_identity_required_query_ids": 3,
    "text_namu_unresolved_query_ids": 23,
}


@dataclass(frozen=True)
class RoutePolicyManifest:
    schema_version: str
    diagnostic_only: bool
    official_metric_input_rows: int
    protected_namespaces_touched: tuple[str, ...]
    xlsx_pending_evidence_query_ids: frozenset[str]
    pdf_policy_excluded_query_ids: frozenset[str]
    pdf_stable_identity_required_query_ids: frozenset[str]
    text_namu_unresolved_query_ids: frozenset[str]

    def __post_init__(self) -> None:
        if self.schema_version != ROUTE_POLICY_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                "unsupported route policy manifest schema_version: "
                f"{self.schema_version!r}"
            )
        if self.diagnostic_only is not True:
            raise ValueError("route policy manifest must be diagnostic_only=true")
        if self.official_metric_input_rows != 0:
            raise ValueError("route policy manifest must keep official_metric_input_rows=0")
        if tuple(self.protected_namespaces_touched) != ():
            raise ValueError("route policy manifest must keep protected_namespaces_touched=[]")

        groups = {
            "xlsx_pending_evidence_query_ids": _clean_id_iterable(
                self.xlsx_pending_evidence_query_ids,
                "xlsx_pending_evidence_query_ids",
            ),
            "pdf_policy_excluded_query_ids": _clean_id_iterable(
                self.pdf_policy_excluded_query_ids,
                "pdf_policy_excluded_query_ids",
            ),
            "pdf_stable_identity_required_query_ids": _clean_id_iterable(
                self.pdf_stable_identity_required_query_ids,
                "pdf_stable_identity_required_query_ids",
            ),
            "text_namu_unresolved_query_ids": _clean_id_iterable(
                self.text_namu_unresolved_query_ids,
                "text_namu_unresolved_query_ids",
            ),
        }
        _reject_cross_group_duplicates(groups)
        _reject_count_drift(groups)
        object.__setattr__(self, "protected_namespaces_touched", ())
        for key, values in groups.items():
            object.__setattr__(self, key, values)


def load_route_policy_manifest(path: Path | str | None = None) -> RoutePolicyManifest:
    if path is None:
        return _load_default_route_policy_manifest()
    return _load_route_policy_manifest_from_path(Path(path))


@lru_cache(maxsize=1)
def _load_default_route_policy_manifest() -> RoutePolicyManifest:
    return _load_route_policy_manifest_from_path(DEFAULT_ROUTE_POLICY_MANIFEST_PATH)


def _load_route_policy_manifest_from_path(path: Path) -> RoutePolicyManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"route policy manifest missing: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("route policy manifest must be a JSON object")
    return _manifest_from_mapping(payload)


def _manifest_from_mapping(payload: Mapping[str, Any]) -> RoutePolicyManifest:
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != ROUTE_POLICY_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "unsupported route policy manifest schema_version: "
            f"{schema_version!r}"
        )
    diagnostic_only = payload.get("diagnostic_only")
    if diagnostic_only is not True:
        raise ValueError("route policy manifest must be diagnostic_only=true")
    if payload.get("official_metric_input_rows") != 0:
        raise ValueError("route policy manifest must keep official_metric_input_rows=0")
    protected_namespaces = payload.get("protected_namespaces_touched")
    if protected_namespaces != []:
        raise ValueError("route policy manifest must keep protected_namespaces_touched=[]")
    groups = {
        "xlsx_pending_evidence_query_ids": _id_set(payload, "xlsx_pending_evidence_query_ids"),
        "pdf_policy_excluded_query_ids": _id_set(payload, "pdf_policy_excluded_query_ids"),
        "pdf_stable_identity_required_query_ids": _id_set(payload, "pdf_stable_identity_required_query_ids"),
        "text_namu_unresolved_query_ids": _id_set(payload, "text_namu_unresolved_query_ids"),
    }
    _reject_cross_group_duplicates(groups)
    return RoutePolicyManifest(
        schema_version=schema_version,
        diagnostic_only=True,
        official_metric_input_rows=0,
        protected_namespaces_touched=(),
        xlsx_pending_evidence_query_ids=groups["xlsx_pending_evidence_query_ids"],
        pdf_policy_excluded_query_ids=groups["pdf_policy_excluded_query_ids"],
        pdf_stable_identity_required_query_ids=groups["pdf_stable_identity_required_query_ids"],
        text_namu_unresolved_query_ids=groups["text_namu_unresolved_query_ids"],
    )


def _id_set(payload: Mapping[str, Any], key: str) -> frozenset[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"route policy manifest field must be a string list: {key}")
    return _clean_id_iterable(value, key)


def _clean_id_iterable(value: Any, key: str) -> frozenset[str]:
    if isinstance(value, str) or not isinstance(value, (frozenset, list, set, tuple)):
        raise ValueError(f"route policy manifest field must be a string list: {key}")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"route policy manifest field must be a string list: {key}")
    cleaned = [item.strip() for item in value if item.strip()]
    if len(cleaned) != len(value):
        raise ValueError(f"route policy manifest field contains blank query id: {key}")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"route policy manifest field contains duplicate query id: {key}")
    return frozenset(cleaned)


def _reject_count_drift(groups: Mapping[str, frozenset[str]]) -> None:
    for key, expected in EXPECTED_ROUTE_POLICY_QUERY_ID_COUNTS.items():
        actual = len(groups.get(key, ()))
        if actual != expected:
            raise ValueError(
                "route policy manifest field has unexpected query id count: "
                f"{key} expected {expected}, got {actual}"
            )


def _reject_cross_group_duplicates(groups: Mapping[str, frozenset[str]]) -> None:
    owner_by_id: dict[str, str] = {}
    for key, values in groups.items():
        for value in values:
            previous = owner_by_id.setdefault(value, key)
            if previous != key:
                raise ValueError(
                    "route policy manifest query id appears in multiple fields: "
                    f"{value}"
                )
