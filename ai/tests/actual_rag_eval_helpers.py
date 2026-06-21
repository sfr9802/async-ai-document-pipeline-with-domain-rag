from __future__ import annotations

import json
from pathlib import Path


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def output_file_names(path: Path) -> list[str]:
    return sorted(item.name for item in path.iterdir() if item.is_file())


class FakeBgeM3EmbeddingProvider:
    model_name = "BAAI/bge-m3-test"

    def embed_passages(self, texts: list[str]) -> object:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> object:
        return self._embed(texts)

    def _embed(self, texts: list[str]) -> object:
        import numpy as np

        rows: list[list[float]] = []
        for text in texts:
            lower = text.casefold()
            rows.append(
                [
                    1.0 if "orion" in lower else 0.0,
                    1.0 if "atlas" in lower else 0.0,
                    1.0 if "april" in lower or "2026" in lower else 0.0,
                    1.0,
                ]
            )
        matrix = np.asarray(rows, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class FakeWeaviateBgeM3EmbeddingProvider(FakeBgeM3EmbeddingProvider):
    model_name = "BAAI/bge-m3"
    device = "cuda:0"


def weaviate_source_atom_record(index: int, *, text: str | None = None) -> dict:
    return {
        "source_atom_id": f"srcatom-index-{index}",
        "evidence_bundle_id": f"bundle-index-{index}",
        "doc_id": "doc-index",
        "chunk_id": f"chunk-index-{index}",
        "source_family": "TEXT",
        "source_track": "namu",
        "title": "Project Orion",
        "section": "Launch",
        "text": text or f"Project Orion checkpoint batch text {index}.",
        "text_sha256": f"sha-index-{index}",
        "source_uri_hash": "uri-sha",
        "source_hash": "source-sha",
        "ingestion_run_id": "ingestion-nonprod",
        "ingestion_version": "v1",
        "namespace": "actual_rag_eval_nonprod",
        "visibility": "nonprod",
    }


def _minimal_agentic_planner_guardrail_summary() -> dict[str, object]:
    planner = {
        "schema_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "planner_enabled": True,
        "planner_mode": "dry-run",
        "planner_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "ran_after_selected_evidence_composer": True,
        "ran_after_evidence_gate": True,
        "planner_decision_count": 1,
        "planner_action_counts": {"deterministic_abstain": 1},
        "planner_failure_class_counts": {"no_safe_action": 1},
        "planner_no_safe_action_count": 1,
        "planner_forbidden_shortcut_detected_count": 0,
        "planner_expected_extra_query_count": 0,
        "planner_expected_tool_call_count": 0,
        "planner_expected_llm_retry_count": 0,
        "planner_heuristic_risk_class": "diagnostic_probe_only",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "retrieved_context_only_citation_policy": "diagnostic_only_never_promoted",
        "planner_execution": {
            "retrieval_executed": False,
            "tool_call_executed": False,
            "llm_retry_executed": False,
            "extra_query_count_executed": 0,
            "tool_call_count_executed": 0,
            "llm_retry_count_executed": 0,
        },
        "guardrail_flags": {
            "gold_or_qrels_mutation": False,
            "expected_fields_used_for_planner_selection": False,
            "query_id_used_for_planner_selection": False,
            "row_id_used_for_planner_selection": False,
            "target_id_used_for_planner_selection": False,
            "qrels_used_for_planner_selection": False,
            "labels_used_for_planner_selection": False,
            "baseline_topk_or_legacy_outputs_used": False,
            "row_specific_alias_or_shortcut_used": False,
            "retrieval_executed": False,
            "tool_call_executed": False,
            "llm_retry_executed": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "evidence_gate_loosened": False,
            "retrieved_context_only_citation_promoted": False,
            "official_metric": False,
            "production_routing_opened": False,
            "protected_namespace_mutation": False,
        },
        "gate_before": {"allowed_answer_count": 5, "unsupported_answer_blocked_count": 1},
        "gate_after_unchanged_because_dry_run": {"allowed_answer_count": 5, "unsupported_answer_blocked_count": 1},
        "decisions": [
            {
                "item_index": 0,
                "query_sha256": "sha256:test",
                "query_preview": "test",
                "failure_class": "no_safe_action",
                "proposed_action": "deterministic_abstain",
                "expected_extra_query_count": 0,
                "expected_tool_call_count": 0,
                "expected_llm_retry_count": 0,
                "executed": False,
            }
        ],
    }
    return {
        "run_id": "guarded_planner",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "agentic_planner_dry_run": planner,
    }
