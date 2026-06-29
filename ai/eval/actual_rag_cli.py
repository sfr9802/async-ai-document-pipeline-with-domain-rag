from __future__ import annotations

from ai.eval.actual_rag_core_base import *
from ai.eval.actual_rag_core_xlsx import *
from ai.eval.actual_rag_core_quality import *
from ai.eval.actual_rag_runner import *

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pragmatic actual RAG eval metric generation")
    parser.add_argument("--dataset", required=True, help="Eval dataset JSONL/JSON path")
    parser.add_argument("--index", default="current", help="Index/path/name label to record in reports")
    parser.add_argument(
        "--context-jsonl",
        default="",
        help="Optional deterministic per-item RAG output/context JSONL for smoke tests or precomputed runs",
    )
    parser.add_argument("--output-mode", default="single", choices=["single", "legacy", "both", "runstore"])
    parser.add_argument("--retrieval-backend", default="auto", choices=list(RAG_RETRIEVAL_BACKEND_CHOICES))
    parser.add_argument(
        "--retrieval-surface",
        default="auto",
        choices=["auto", "searchunit-searchview", "source-native", "source-atom", "evidence-bundle"],
        help="Retrieval corpus surface; auto prefers SourceAtom/EvidenceBundle source-native units when available.",
    )
    parser.add_argument(
        "--legacy-surface-comparison",
        action="store_true",
        help="Run SearchUnit/SearchView as an explicit legacy diagnostic comparison; it is not a routine auto candidate surface.",
    )
    parser.add_argument(
        "--source-native-index-dir",
        default="",
        help="Optional source-native index directory containing search_view_manifest.jsonl, build.json, and faiss.index.",
    )
    parser.add_argument(
        "--build-source-native-bge-m3-index",
        action="store_true",
        help="Build the additive non-production source-native BGE-M3 FAISS index before running evaluation.",
    )
    parser.add_argument(
        "--force-source-native-bge-m3-index-rebuild",
        action="store_true",
        help="Rebuild the additive non-production source-native BGE-M3 FAISS index even when artifacts already exist.",
    )
    parser.add_argument("--use-fake-vector-adapter", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--use-fake-source-native-fixture", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory; defaults to reports/rag_eval/<run_id>",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--judge-mode", default="heuristic", choices=["heuristic", "local-llm"])
    parser.add_argument("--judge-backend", default="", choices=["", "llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--judge-base-url", default="")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-threshold", type=float, default=0.5)
    parser.add_argument("--judge-timeout-seconds", type=int, default=60)
    parser.add_argument("--judge-max-tokens", type=int, default=360)
    parser.add_argument("--skip-judge-endpoint-check", action="store_true")
    parser.add_argument(
        "--provisional-require-citations",
        action="store_true",
        help="Require strict citation pass for e2e_rag_success_provisional; default keeps citation checks separate.",
    )
    parser.add_argument(
        "--resolve-expected-evidence",
        action="store_true",
        default=True,
        help="Run diagnostic expected-evidence resolution; enabled by default for source-native full-corpus review-only lookup.",
    )
    parser.add_argument(
        "--no-resolve-expected-evidence",
        action="store_false",
        dest="resolve_expected_evidence",
        help="Disable expected-evidence resolution diagnostics.",
    )
    parser.add_argument(
        "--evidence-resolution-scope",
        default="full-corpus",
        choices=["retrieved-only", "index-candidate-lookup", "both", "full-corpus", "full-corpus-review-only"],
        help="Candidate source for expected-evidence resolution diagnostics.",
    )
    parser.add_argument("--max-evidence-candidates", type=int, default=5)
    parser.add_argument("--min-evidence-resolution-score", type=float, default=0.35)
    parser.add_argument(
        "--count-medium-evidence-resolution",
        action="store_true",
        help="Count medium-confidence evidence resolution candidates as resolved in provisional resolved-evidence metrics.",
    )
    parser.add_argument(
        "--write-evidence-mapping-packet",
        action="store_true",
        help="Deprecated alias for writing a single human review packet in single mode; legacy packet sidecars require --output-mode legacy.",
    )
    parser.add_argument(
        "--write-human-review-packet",
        action="store_true",
        help="Write exactly one additional human review CSV packet with blank human-owned fields.",
    )
    parser.add_argument(
        "--reviewed-evidence-mapping-csv",
        default="",
        help="Explicit human-reviewed evidence mapping CSV to apply as a run-local derived overlay; never overwrites the dataset.",
    )
    parser.add_argument(
        "--compare-to",
        default="",
        help="Compare this run to a summary JSON/run directory, or to 'latest'/'previous'.",
    )
    parser.add_argument(
        "--portfolio-comparison-report",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help=(
            "Embed a non-production portfolio comparison against another report.json in this run's report.json. "
            "May be repeated; compared reports are post-run evidence only and never generation inputs."
        ),
    )
    parser.add_argument(
        "--write-portfolio-experiment-summary",
        action="store_true",
        help=(
            "Write portfolio_experiment_summary.md from the embedded portfolio comparison. "
            "Requires at least one --portfolio-comparison-report."
        ),
    )
    parser.add_argument(
        "--quality-gate-baseline",
        default="",
        help="Frozen legacy SearchUnit/SearchView report path, run directory, or 'auto' for post-run quality-gate parity artifacts.",
    )
    parser.add_argument(
        "--evidence-gate-mode",
        default="off",
        choices=["off", "diagnostic", "enforce"],
        help="Bounded SourceAtom/EvidenceBundle evidence gate: off preserves answers, diagnostic reports decisions, enforce abstains unsupported answers.",
    )
    parser.add_argument(
        "--agentic-planner-mode",
        default="off",
        choices=list(AGENTIC_PLANNER_MODE_CHOICES),
        help=(
            "Non-production planner checkpoint; dry-run records one proposed post-gate action per failed row "
            "without executing retrieval, tools, or LLM retry."
        ),
    )
    parser.add_argument(
        "--xlsx-locator-tool-execute-once",
        action="store_true",
        help=(
            "Explicit non-production XLSX locator checkpoint; executes one source-owned locator tool call per eligible "
            "post-gate XLSX residual and writes typed diagnostics to run.sqlite."
        ),
    )
    parser.add_argument(
        "--llm-query-anchor-classifier",
        action="store_true",
        help="Optional non-production query-text-only local LLM classifier that can remove intent anchors only.",
    )
    parser.add_argument(
        "--answer-composer",
        default="extractive-v1",
        choices=sorted(ANSWER_COMPOSER_PROVIDERS),
        help="Answer composer for explicit non-production experiments; selected-evidence mode rewrites answers/citations from selected SourceAtom/EvidenceBundle evidence only.",
    )
    parser.add_argument(
        "--selected-evidence-citation-format",
        default="compact",
        choices=sorted(SELECTED_EVIDENCE_CITATION_FORMATS),
        help="Citation formatter variant for the selected-evidence composer; display-only and still validated by the evidence gate.",
    )
    parser.add_argument(
        "--selected-evidence-composer-retry-mode",
        default="off",
        choices=sorted(SELECTED_EVIDENCE_COMPOSER_RETRY_MODES),
        help="Optional bounded retry for selected-evidence local composer; bounded-once retries only after evidence-gate insufficiency.",
    )
    parser.add_argument(
        "--local-llm-composer-backend",
        default="",
        choices=["", "llamacpp", "openai-compatible", "ollama"],
        help="Optional localhost-only backend for selected-evidence-local-llm-v1.",
    )
    parser.add_argument(
        "--local-llm-composer-base-url",
        default="",
        help="Optional localhost-only base URL for selected-evidence-local-llm-v1; external endpoints are rejected.",
    )
    parser.add_argument(
        "--local-llm-composer-model",
        default="",
        help="Optional local model name for selected-evidence-local-llm-v1.",
    )
    parser.add_argument("--local-llm-composer-timeout-seconds", type=int, default=60)
    parser.add_argument("--local-llm-composer-max-tokens", type=int, default=360)
    parser.add_argument("--skip-local-llm-composer-endpoint-check", action="store_true")
    parser.add_argument(
        "--weaviate-route-ab-mode",
        default="",
        help=(
            "Explicit non-production Weaviate route A/B comparison modes, comma-separated: "
            "text,mixed,routed. Writes route-selected comparison sidecars only when set."
        ),
    )
    parser.add_argument(
        "--corpus-coverage-audit-query-id",
        action="append",
        default=[],
        help=(
            "Embed a report-only corpus coverage audit for a target query id. "
            "May be repeated; does not mutate gold/qrels/labels or write sidecars."
        ),
    )
    parser.add_argument(
        "--corpus-coverage-audit-target-anchor",
        action="append",
        default=[],
        help=(
            "Target anchor for the report-only corpus coverage audit. "
            "May be repeated; required for any target query id audit."
        ),
    )
    parser.add_argument(
        "--write-latest",
        action="store_true",
        help="Update latest pointer JSON files under the report root after a successful run.",
    )
    parser.add_argument(
        "--append-registry",
        action="store_true",
        help="Append runs.jsonl and compact status.jsonl events after a successful run.",
    )
    parser.add_argument(
        "--report-root",
        default=str(REPORT_ROOT),
        help="Report root for registry/latest pointers; defaults to reports/rag_eval.",
    )
    parser.add_argument(
        "--status-jsonl",
        default=str(STATUS_JSONL_PATH),
        help="Status JSONL path for compact actual-RAG run events.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    generated_at = utc_now_iso()
    report_root = Path(args.report_root)
    try:
        run_id = make_actual_rag_run_id(
            Path(args.dataset),
            explicit_run_id=args.run_id,
            generated_at=generated_at,
            report_root=report_root,
        )
    except DatasetSchemaError as exc:
        print(f"dataset schema error: {exc}", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir) if _clean(args.output_dir) else report_root / run_id
    command = "python -m ai.scripts.rag_actual_eval " + " ".join(sys.argv[1:] if argv is None else argv)
    source_native_units: list[dict[str, Any]] | None = None
    searchunit_units: list[dict[str, Any]] | None = None
    source_native_embedding_provider: Any | None = None
    source_native_index_dir_for_run: Path | None = Path(args.source_native_index_dir) if _clean(args.source_native_index_dir) else None
    source_native_index_build: dict[str, Any] | None = None
    if args.use_fake_source_native_fixture:
        source_native_units = [
            {
                "unit_id": "fake-source-native-1",
                "source_atom_id": "fake-source-atom-1",
                "doc_id": "fake-source-doc",
                "chunk_id": "fake-source-chunk",
                "source_family": "TEXT",
                "title": "Fake Source Native",
                "section": "Evidence",
                "text": "needle answer appears in source native evidence",
                "surface": "source_atom",
                "text_sha256": _sha256_text("needle answer appears in source native evidence"),
                "metadata": {"fixture": "fake_source_native"},
            }
        ]
        searchunit_units = [
            {
                "payload_id": "fake-searchunit-1",
                "search_unit_id": "fake-searchunit-chunk",
                "search_view_id": "fake-searchunit-view",
                "source_family": "TEXT",
                "bm25_text": "irrelevant legacy projection filler",
                "embedding_text": "irrelevant legacy projection filler",
                "metadata": {"source_safe_id": "fake-searchunit-doc", "source_text_sha256": "fake-searchunit-sha"},
            }
        ]
        source_native_embedding_provider = FakeDeterministicEmbeddingProvider()
    try:
        if args.build_source_native_bge_m3_index:
            target_index_dir = source_native_index_dir_for_run or SOURCE_NATIVE_BGE_M3_INDEX_DIR
            source_native_index_build = build_source_native_bge_m3_index_artifact(
                index_dir=target_index_dir,
                force=args.force_source_native_bge_m3_index_rebuild,
                gpu_preflight=build_gpu_preflight(),
            )
            source_native_index_dir_for_run = target_index_dir
        comparison_summary, comparison_target = resolve_comparison_summary(
            args.compare_to,
            dataset_path=Path(args.dataset),
            report_root=report_root,
        )
        bundle = run_eval_from_paths(
            dataset_path=Path(args.dataset),
            output_dir=output_dir,
            context_jsonl_path=Path(args.context_jsonl) if _clean(args.context_jsonl) else None,
            index=args.index,
            top_k=args.top_k,
            run_id=run_id,
            command=command,
            judge_mode=args.judge_mode,
            judge_backend=args.judge_backend,
            judge_base_url=args.judge_base_url,
            judge_model=args.judge_model,
            judge_threshold=args.judge_threshold,
            judge_timeout_seconds=args.judge_timeout_seconds,
            judge_max_tokens=args.judge_max_tokens,
            skip_judge_endpoint_check=args.skip_judge_endpoint_check,
            provisional_require_citations=args.provisional_require_citations,
            generated_at=generated_at,
            comparison_summary=comparison_summary,
            comparison_target=comparison_target or args.compare_to,
            portfolio_comparison_reports=args.portfolio_comparison_report,
            write_portfolio_experiment_summary=args.write_portfolio_experiment_summary,
            report_root=report_root,
            status_jsonl_path=Path(args.status_jsonl),
            append_registry=args.append_registry,
            write_latest=args.write_latest,
            resolve_expected_evidence=args.resolve_expected_evidence,
            evidence_resolution_scope=args.evidence_resolution_scope,
            max_evidence_candidates=args.max_evidence_candidates,
            min_evidence_resolution_score=args.min_evidence_resolution_score,
            count_medium_evidence_resolution=args.count_medium_evidence_resolution,
            write_evidence_mapping_packet=args.write_evidence_mapping_packet,
            write_human_review_packet=args.write_human_review_packet,
            reviewed_evidence_mapping_csv=Path(args.reviewed_evidence_mapping_csv)
            if _clean(args.reviewed_evidence_mapping_csv)
            else None,
            output_mode=args.output_mode,
            retrieval_surface=args.retrieval_surface,
            retrieval_backend=args.retrieval_backend,
            legacy_surface_comparison=args.legacy_surface_comparison,
            source_native_units=source_native_units,
            searchunit_units=searchunit_units,
            source_native_embedding_provider=source_native_embedding_provider,
            source_native_index_dir=source_native_index_dir_for_run,
            source_native_index_build=source_native_index_build,
            quality_gate_baseline_path=args.quality_gate_baseline,
            evidence_gate_mode=args.evidence_gate_mode,
            agentic_planner_mode=args.agentic_planner_mode,
            xlsx_locator_tool_execute_once=args.xlsx_locator_tool_execute_once,
            llm_query_anchor_classifier=args.llm_query_anchor_classifier,
            answer_composer=args.answer_composer,
            selected_evidence_citation_format=args.selected_evidence_citation_format,
            selected_evidence_composer_retry_mode=args.selected_evidence_composer_retry_mode,
            local_llm_composer_backend=args.local_llm_composer_backend,
            local_llm_composer_base_url=args.local_llm_composer_base_url,
            local_llm_composer_model=args.local_llm_composer_model,
            local_llm_composer_timeout_seconds=args.local_llm_composer_timeout_seconds,
            local_llm_composer_max_tokens=args.local_llm_composer_max_tokens,
            skip_local_llm_composer_endpoint_check=args.skip_local_llm_composer_endpoint_check,
            weaviate_route_ab_mode=args.weaviate_route_ab_mode,
            corpus_coverage_audit_query_ids=args.corpus_coverage_audit_query_id,
            corpus_coverage_audit_target_anchors=args.corpus_coverage_audit_target_anchor,
            retrieval_adapter=FakeVectorAdapter(requested_backend=args.retrieval_backend)
            if args.use_fake_vector_adapter
            else None,
        )
    except DatasetSchemaError as exc:
        print(f"dataset schema error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"execution error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": run_id,
                "report_json": _artifact_path(bundle.summary, "report_json"),
                "summary_json": _artifact_path(bundle.summary, "summary_json"),
                "items_jsonl": _artifact_path(bundle.summary, "items_jsonl"),
                "markdown_report": _artifact_path(bundle.summary, "markdown_report"),
                "xlsx_locator_run_sqlite": _artifact_path(bundle.summary, "xlsx_locator_run_sqlite"),
                "human_review_packet_csv": _artifact_path(bundle.summary, "human_review_packet_csv"),
                "evidence_mapping_review_packet_csv": _artifact_path(bundle.summary, "evidence_mapping_review_packet_csv"),
                "evidence_mapping_review_packet_jsonl": _artifact_path(bundle.summary, "evidence_mapping_review_packet_jsonl"),
                "evidence_mapping_review_packet_md": _artifact_path(bundle.summary, "evidence_mapping_review_packet_md"),
                "evidence_mapping_packet_summary_json": _artifact_path(bundle.summary, "evidence_mapping_packet_summary_json"),
                "portfolio_experiment_summary_md": _artifact_path(bundle.summary, "portfolio_experiment_summary_md"),
                "retrieval_backend": bundle.summary.get("retrieval_backend"),
                "retrieval_surface": bundle.summary.get("retrieval_surface"),
                "retrieval_surface_decision": bundle.summary.get("retrieval_surface_decision"),
                "surface_migration": bundle.summary.get("surface_migration"),
                "source_native_index_build": bundle.summary.get("source_native_index_build"),
                "evidence_gate": bundle.summary.get("evidence_gate"),
                "legacy_real_rag_quality_gate_report_json": _artifact_path(
                    bundle.summary,
                    "legacy_real_rag_quality_gate_report_json",
                ),
                "legacy_real_rag_quality_gate_items_jsonl": _artifact_path(
                    bundle.summary,
                    "legacy_real_rag_quality_gate_items_jsonl",
                ),
                "registry_jsonl": (report_root / REGISTRY_FILENAME).as_posix() if args.append_registry else "",
                "latest_json": (report_root / "latest.json").as_posix() if args.write_latest else "",
                "status_jsonl": str(Path(args.status_jsonl)) if args.append_registry else "",
                "comparison_target": (bundle.summary.get("comparison") or {}).get("target_run_id")
                if isinstance(bundle.summary.get("comparison"), Mapping)
                else None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _synchronize_actual_rag_namespaces() -> None:
    import ai.eval.actual_rag_core_base as _base
    import ai.eval.actual_rag_core_xlsx as _xlsx
    import ai.eval.actual_rag_core_quality as _quality
    import ai.eval.actual_rag_runner as _runner
    import ai.eval.actual_rag_cli as _cli

    modules = (_base, _xlsx, _quality, _runner, _cli)
    merged = {}
    for module in modules:
        merged.update(
            {
                name: value
                for name, value in module.__dict__.items()
                if name not in {"_base", "_xlsx", "_quality", "_runner", "_cli", "modules", "merged"}
                and not (name.startswith("__") and name.endswith("__"))
            }
        )
    for module in modules:
        module.__dict__.update(merged)


_synchronize_actual_rag_namespaces()


_synchronize_actual_rag_namespaces()
if __name__ == "__main__":
    raise SystemExit(main())
