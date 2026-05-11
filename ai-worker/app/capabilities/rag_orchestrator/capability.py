"""Feature-flagged worker capability for the query-time RAG orchestrator POC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.capabilities.base import (
    Capability,
    CapabilityError,
    CapabilityInput,
    CapabilityInputArtifact,
    CapabilityOutput,
    CapabilityOutputArtifact,
)
from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.graph import run_query_orchestrator_pure

CAPABILITY_NAME = "RAG_QUERY_ORCHESTRATOR"
RESULT_ARTIFACT_TYPE = "RAG_QUERY_ORCHESTRATOR_RESULT"
REQUEST_ARTIFACT_TYPES = {
    "RAG_QUERY_ORCHESTRATOR_REQUEST",
    "INPUT_JSON",
    "INPUT_TEXT",
}

OrchestratorMode = Literal["test", "production"]


@dataclass(frozen=True)
class RagQueryOrchestratorCapabilityConfig:
    enabled: bool = False
    mode: OrchestratorMode = "test"


class RagQueryOrchestratorCapability(Capability):
    """Run the query-time RAG orchestrator POC behind an explicit flag."""

    name = CAPABILITY_NAME

    def __init__(self, *, config: RagQueryOrchestratorCapabilityConfig) -> None:
        self._config = config

    def run(self, input: CapabilityInput) -> CapabilityOutput:
        if not self._config.enabled:
            return _json_output(
                {
                    "status": "disabled",
                    "capability": self.name,
                    "reason": "feature_flag_off",
                }
            )

        request = _extract_request(input)
        query = _string(request.get("query"))
        if not query:
            raise CapabilityError(
                "RAG_QUERY_ORCHESTRATOR_EMPTY_QUERY",
                "RAG_QUERY_ORCHESTRATOR request requires a non-empty query.",
            )

        mode = _mode(request.get("mode"), default=self._config.mode)
        policy = _policy_from_snapshot(
            request.get("policy") or request.get("queryPolicy"),
            request_id=input.job_id,
        )
        _validate_mode_policy(mode=mode, policy=policy)

        state = run_query_orchestrator_pure(query=query, policy=policy)
        return _json_output(
            {
                "status": "ok",
                "capability": self.name,
                "mode": mode,
                "graph_backend": "pure_fake_graph",
                "runtime_endpoint": False,
                "langchain_used": False,
                "query": query,
                "policy": policy.to_dict(),
                "state": _state_to_dict(state),
            }
        )


def _extract_request(input: CapabilityInput) -> Mapping[str, Any]:
    for artifact in input.inputs:
        if artifact.type in REQUEST_ARTIFACT_TYPES:
            return _decode_request_artifact(artifact)
    raise CapabilityError(
        "RAG_QUERY_ORCHESTRATOR_REQUEST_REQUIRED",
        "RAG_QUERY_ORCHESTRATOR requires a JSON request artifact with query and policy.",
    )


def _decode_request_artifact(artifact: CapabilityInputArtifact) -> Mapping[str, Any]:
    try:
        text = artifact.content.decode("utf-8").strip()
    except UnicodeDecodeError as ex:
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_BAD_REQUEST",
            "RAG_QUERY_ORCHESTRATOR request artifact must be UTF-8 JSON.",
        ) from ex

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as ex:
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_BAD_REQUEST",
            "RAG_QUERY_ORCHESTRATOR request artifact must be JSON.",
        ) from ex

    if not isinstance(payload, Mapping):
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_BAD_REQUEST",
            "RAG_QUERY_ORCHESTRATOR request JSON must be an object.",
        )
    return payload


def _policy_from_snapshot(raw: Any, *, request_id: str) -> QueryPolicy:
    if not isinstance(raw, Mapping):
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_INVALID_POLICY",
            "RAG_QUERY_ORCHESTRATOR request requires a policy snapshot object.",
        )

    try:
        return QueryPolicy(
            request_id=_string(_get_any(raw, "request_id", "requestId")) or request_id,
            user_id=_optional_string(_get_any(raw, "user_id", "userId")),
            tenant_id=_optional_string(_get_any(raw, "tenant_id", "tenantId")),
            acl_tags=_list_str(_get_any(raw, "acl_tags", "aclTags")),
            required_index_version=_string(
                _get_any(raw, "required_index_version", "requiredIndexVersion")
            ),
            allowed_source_file_types=_list_str(
                _get_any(raw, "allowed_source_file_types", "allowedSourceFileTypes")
            ),
            allowed_parser_versions=_list_str(
                _get_any(raw, "allowed_parser_versions", "allowedParserVersions")
            ),
            required_embedding_status=_string(
                _get_any(
                    raw,
                    "required_embedding_status",
                    "requiredEmbeddingStatus",
                ),
                fallback="EMBEDDED",
            ),
            top_k=int(_get_any(raw, "top_k", "topK") or 5),
        )
    except (TypeError, ValueError) as ex:
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_INVALID_POLICY",
            f"Invalid RAG_QUERY_ORCHESTRATOR policy snapshot: {ex}",
        ) from ex


def _validate_mode_policy(*, mode: OrchestratorMode, policy: QueryPolicy) -> None:
    if mode == "test":
        return

    missing = []
    if not policy.user_id:
        missing.append("user_id")
    if not policy.tenant_id:
        missing.append("tenant_id")
    if not policy.acl_tags:
        missing.append("acl_tags")
    if missing:
        raise CapabilityError(
            "RAG_QUERY_ORCHESTRATOR_PRODUCTION_CONTEXT_REQUIRED",
            "Production RAG_QUERY_ORCHESTRATOR runs require "
            + ", ".join(missing)
            + ".",
        )


def _state_to_dict(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": state.get("request_id"),
        "query": state.get("query"),
        "normalized_query": state.get("normalized_query"),
        "intent": state.get("intent"),
        "route_decision": dict(state.get("route_decision", {})),
        "selected_tools": list(state.get("selected_tools", [])),
        "fallback_routes_triggered": list(state.get("fallback_routes_triggered", [])),
        "tool_results": [
            item.to_dict() for item in state.get("tool_results", [])
        ],
        "evidence": [item.to_dict() for item in state.get("evidence", [])],
        "merged_evidence": [
            item.to_dict() for item in state.get("merged_evidence", [])
        ],
        "verified_evidence": [
            item.to_dict() for item in state.get("verified_evidence", [])
        ],
        "rejected_evidence": list(state.get("rejected_evidence", [])),
        "aggregation_results": [
            item.to_dict() for item in state.get("aggregation_results", [])
        ],
        "answer": dict(state.get("answer", {})),
        "stop_reason": state.get("stop_reason"),
        "trace": list(state.get("trace", [])),
        "errors": list(state.get("errors", [])),
    }


def _json_output(body: Mapping[str, Any]) -> CapabilityOutput:
    return CapabilityOutput(
        outputs=[
            CapabilityOutputArtifact(
                type=RESULT_ARTIFACT_TYPE,
                filename="rag_query_orchestrator_result.json",
                content_type="application/json; charset=utf-8",
                content=json.dumps(body, ensure_ascii=False, sort_keys=True).encode(
                    "utf-8"
                ),
            )
        ]
    )


def _mode(value: Any, *, default: OrchestratorMode) -> OrchestratorMode:
    raw = _string(value, fallback=default).lower()
    if raw in {"test", "production"}:
        return raw  # type: ignore[return-value]
    raise CapabilityError(
        "RAG_QUERY_ORCHESTRATOR_BAD_REQUEST",
        "RAG_QUERY_ORCHESTRATOR mode must be 'test' or 'production'.",
    )


def _get_any(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _list_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("policy list fields must be strings or lists of strings")


def _string(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _optional_string(value: Any) -> str | None:
    text = _string(value)
    return text or None
