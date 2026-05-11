from __future__ import annotations

import json

import pytest

from app.capabilities.base import (
    CapabilityError,
    CapabilityInput,
    CapabilityInputArtifact,
)
from app.capabilities.rag_orchestrator.capability import (
    CAPABILITY_NAME,
    RESULT_ARTIFACT_TYPE,
)
from app.core.config import WorkerSettings


def test_feature_flag_off_keeps_existing_registry_behavior(monkeypatch):
    from app.capabilities import registry as registry_module

    def _should_not_be_called(_settings):
        raise AssertionError("orchestrator builder must not run while flag is off")

    monkeypatch.setattr(
        registry_module,
        "_build_rag_query_orchestrator_capability",
        _should_not_be_called,
    )
    settings = _settings(
        rag_query_orchestrator_enabled=False,
        xlsx_extract_enabled=True,
    )

    result = registry_module.build_default_registry(settings)

    assert result.available() == ["MOCK", "XLSX_EXTRACT"]


def test_feature_flag_off_does_not_register_or_execute_capability():
    from app.capabilities import registry as registry_module

    result = registry_module.build_default_registry(
        _settings(rag_query_orchestrator_enabled=False)
    )

    assert CAPABILITY_NAME not in result.available()
    with pytest.raises(CapabilityError) as ex_info:
        result.get(CAPABILITY_NAME)
    assert ex_info.value.code == "UNKNOWN_CAPABILITY"


def test_feature_flag_on_registers_capability():
    from app.capabilities import registry as registry_module

    result = registry_module.build_default_registry(
        _settings(rag_query_orchestrator_enabled=True)
    )

    assert result.available() == ["MOCK", CAPABILITY_NAME]


def test_test_mode_policy_runs_fake_tool_graph():
    from app.capabilities import registry as registry_module

    registry = registry_module.build_default_registry(
        _settings(rag_query_orchestrator_enabled=True)
    )
    capability = registry.get(CAPABILITY_NAME)

    output = capability.run(
        _input(
            {
                "query": "pdf와 xlsx 표 합계를 같이 확인해줘",
                "mode": "test",
                "policy": _policy_snapshot(),
            }
        )
    )
    body = _body(output)

    assert output.outputs[0].type == RESULT_ARTIFACT_TYPE
    assert body["status"] == "ok"
    assert body["graph_backend"] == "pure_fake_graph"
    assert body["runtime_endpoint"] is False
    assert body["langchain_used"] is False
    assert body["state"]["selected_tools"] == ["pdf", "xlsx"]
    route_decision = body["state"]["route_decision"]
    assert route_decision["route"] == "multi_route"
    assert route_decision["routes"] == [
        "pdf_business_ocr_mm",
        "xlsx_business_structured",
    ]
    assert route_decision["required_evidence_type"] == "multi_track_evidence_bundle"
    assert route_decision["route_confidence"] > 0.5
    assert route_decision["allow_fallback"] is False
    assert body["state"]["fallback_routes_triggered"] == []
    assert body["state"]["verified_evidence"]
    assert body["state"]["answer"]["status"] == "stub"
    assert body["state"]["aggregation_results"]


def test_missing_required_index_version_is_rejected():
    from app.capabilities import registry as registry_module

    capability = registry_module.build_default_registry(
        _settings(rag_query_orchestrator_enabled=True)
    ).get(CAPABILITY_NAME)
    policy = _policy_snapshot()
    policy.pop("requiredIndexVersion")

    with pytest.raises(CapabilityError) as ex_info:
        capability.run(_input({"query": "pdf", "policy": policy}))

    assert ex_info.value.code == "RAG_QUERY_ORCHESTRATOR_INVALID_POLICY"
    assert "required_index_version" in ex_info.value.message


def test_missing_allowed_source_file_types_is_rejected():
    from app.capabilities import registry as registry_module

    capability = registry_module.build_default_registry(
        _settings(rag_query_orchestrator_enabled=True)
    ).get(CAPABILITY_NAME)
    policy = _policy_snapshot()
    policy.pop("allowedSourceFileTypes")

    with pytest.raises(CapabilityError) as ex_info:
        capability.run(_input({"query": "pdf", "policy": policy}))

    assert ex_info.value.code == "RAG_QUERY_ORCHESTRATOR_INVALID_POLICY"
    assert "allowed_source_file_types" in ex_info.value.message


def test_production_mode_requires_tenant_acl_context():
    from app.capabilities import registry as registry_module

    capability = registry_module.build_default_registry(
        _settings(
            rag_query_orchestrator_enabled=True,
            rag_query_orchestrator_mode="production",
        )
    ).get(CAPABILITY_NAME)

    with pytest.raises(CapabilityError) as ex_info:
        capability.run(
            _input(
                {
                    "query": "pdf",
                    "mode": "production",
                    "policy": _policy_snapshot(),
                }
            )
        )

    assert (
        ex_info.value.code
        == "RAG_QUERY_ORCHESTRATOR_PRODUCTION_CONTEXT_REQUIRED"
    )
    assert "tenant_id" in ex_info.value.message
    assert "acl_tags" in ex_info.value.message


def _settings(**overrides) -> WorkerSettings:
    values = {
        "rag_enabled": False,
        "ocr_enabled": False,
        "ocr_extract_enabled": False,
        "xlsx_extract_enabled": False,
        "pdf_extract_enabled": False,
        "multimodal_enabled": False,
    }
    values.update(overrides)
    return WorkerSettings(**values)


def _input(payload: dict) -> CapabilityInput:
    return CapabilityInput(
        job_id="job-rag-orchestrator-1",
        capability=CAPABILITY_NAME,
        attempt_no=1,
        inputs=[
            CapabilityInputArtifact(
                artifact_id="request-1",
                type="RAG_QUERY_ORCHESTRATOR_REQUEST",
                content=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
                filename="request.json",
            )
        ],
    )


def _policy_snapshot() -> dict:
    return {
        "requestId": "req-rag-orchestrator-1",
        "requiredIndexVersion": "rag-ingestion-v2-candidate",
        "allowedSourceFileTypes": ["PDF", "SPREADSHEET", "TEXT"],
        "allowedParserVersions": [
            "pdf-extract-v2",
            "xlsx-extract-v2-hidden-safe",
            "text-parser-v0",
        ],
        "requiredEmbeddingStatus": "EMBEDDED",
        "topK": 5,
    }


def _body(output) -> dict:
    assert len(output.outputs) == 1
    return json.loads(output.outputs[0].content.decode("utf-8"))
