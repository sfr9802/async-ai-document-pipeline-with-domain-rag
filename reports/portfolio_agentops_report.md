# Verifiable Document RAG Backend - AgentOps Technical Sidecar

## Project Goal

Document the thin AgentOps control layer behind the current Verifiable Document
RAG Backend portfolio. The primary portfolio narrative stays centered on
evidence-grounded document RAG; this sidecar explains the auditable tool/policy
trace layer over the existing RAG/evaluation pipeline, not a large autonomous
agent framework.

This report is portfolio-facing. It does not open official metrics, mutate
gold/qrels/labels, approve expected answers, approve supporting evidence, move
`current`, claim product success, or claim live production readiness.

## Architecture

```text
Request context
  -> policy check
  -> AgentOps tool registry
  -> scoped retrieval adapter
  -> SourceAtom hydration
  -> EvidenceBundle validation
  -> answerability/relevance gates
  -> diagnostic answer, handoff, or fail-closed decision
  -> trace/report artifact
```

Existing repo foundations:

| Foundation | Concrete artifact |
|---|---|
| SearchUnit/SearchView retrieval surfaces | `ai/app/capabilities/rag/search_unit_indexing.py`, `ai/eval/indexes/*/search_*_manifest.jsonl` |
| Evidence truth | `ai/app/capabilities/rag/source_registry.py`, `ai/app/capabilities/rag_orchestrator/evidence.py` |
| Deterministic runtime loop | `ai/app/capabilities/rag_orchestrator/agent_runtime.py` |
| L0-L8 tool specs | `ai/app/capabilities/rag_orchestrator/tool_registry.py` |
| Portfolio AgentOps adapter | `ai/app/capabilities/rag_orchestrator/agentops_runtime.py` |
| Evaluation/report governance | `ai/eval/rag_eval_registry.py`, `ai/scripts/rag_eval.py`, `docs/rag-ingestion-*.md` |

## Agentic Runtime Loop

Implemented as a deterministic state-machine adapter:

1. Create request context: run id, query, source family, namespace, indexing scope.
2. Apply policy: allowed tools, namespace, indexing scope, evidence requirement, official-vs-diagnostic decision.
3. Select tools: retrieval tool by source family plus evidence validation and answerability classification.
4. Verify that explicit bounded `candidate_source_atom_ids` exist in the provided source registry and declare a source family matching the request.
5. Invoke the existing bounded runtime only after candidate scope is valid.
6. Validate evidence: SourceAtom and EvidenceBundle are the evidence truth; SearchView/vector payload is candidate-only.
7. Gate answerability: machine diagnostic label only, not human gold.
8. Decide final outcome: diagnostic answer, diagnostic-only handoff, or fail-closed.
9. Emit a run-level trace.

## Tool Registry

The AgentOps adapter exposes a minimal registry:

| Tool | Purpose | Scope |
|---|---|---|
| `retrieve_txt_corpus` | TEXT candidate retrieval | non-production RAG namespaces |
| `retrieve_xlsx_table` | XLSX table/range/cell retrieval | non-production RAG namespaces |
| `retrieve_pdf_ocr` | PDF page/OCR retrieval | non-production RAG namespaces |
| `validate_evidence` | SourceAtom/EvidenceBundle validation | evidence required |
| `classify_answerability` | machine diagnostic bounded-context gate | evidence required, not human gold |
| `generate_eval_report` | summarize trace/report decisions | report/status surfaces |

Every AgentOps tool is `diagnostic_only=true` and `official=false` by default.

## Policy / Guardrail Layer

Implemented in `AgentOpsPolicy`:

| Guardrail | Behavior |
|---|---|
| allowed tools | unknown tool names fail closed and clear trace selected tools |
| allowed namespaces | production or unregistered namespaces fail closed |
| indexing scope | production indexing scope fails closed |
| evidence requirement | evidence-only tools fail closed without evidence ids |
| candidate scope | missing ids, malformed candidate records, missing source-family metadata, or source-family mismatches fail closed before runtime tool calls |
| answer format | answer with citations or abstain |
| official request | fail closed unless user-owned gold/qrels/denominator approval exists |
| runtime query id | optional `query_id` must use the same safe-id pattern as `run_id` |
| ambiguous answerability | diagnostic-only or fail-closed, never official |
| retry/fallback | max one retry, no unbounded loop |

## Evidence Contract

The platform separates retrieval candidates from answer evidence:

| Concept | Role |
|---|---|
| SearchUnit | indexable unit |
| SearchView | candidate-only retrieval view |
| SourceAtom | canonical source evidence atom |
| EvidenceBundle | answer-evidence truth used for citation and answer readiness |

Tool outputs do not become Hit@k/MRR/nDCG improvements. Expected answers,
supporting evidence, qrels, relevance labels, and answerability labels are not
used for candidate generation.

## Evaluation Governance

The current diagnostic line keeps official quality claims closed:

| Gate | State |
|---|---|
| official metric | closed unless user-owned approval opens it |
| gold/qrels mutation | closed |
| relevance/answerability labels | human-owned, blank by default |
| answer-quality metric | not computed as an official/product claim |
| denominator policy | not mutated |
| production/live readiness | closed |

Existing v6 packets provide the governance ladder: structured tool taxonomy
(`v6_6`), agentic retry/fail-closed policy (`v6_7`), metric-gated retrieval
quality engineering (`v6_8`), and answer-quality gate packet (`v6_9`).

## Trace Schema

Schema: `docs/agentops_trace_schema.json`; its JSON Schema `$id` points to
the same tracked docs path instead of an untracked `/schemas/...` location.

Sample trace: `reports/agentops_sample_trace.json`

Trace fields include run id, query, request context, selected tools, called
runtime tools, retrieval namespace, indexing scope, evidence ids, machine
diagnostic answerability, relevance left blank, policy decision, diagnostic-only
flag, retry/repair/fallback decision, failure category, final decision, and
report artifact path.

The JSON schema rejects policy-boundary drift such as production retrieval
namespaces, writable indexing scopes, unsafe answer formats, unsupported source
families, or official-request flags. Blocked fail-closed traces use safe
placeholder values for unsupported source family, namespace, indexing scope, and
answer-format fields instead of persisting raw caller strings.
Report artifact paths are deliberately not caller-controlled in persistent
traces: local absolute paths, parent traversal, and ad-hoc report paths fail
closed and are replaced by the canonical portfolio report artifact path.

Persistent trace fields use opaque query/evidence references and safe run ids.
Raw prompts, source identities, workbook names, raw locators, source titles,
expected answers, supporting evidence, hidden reasoning, local-path-like run ids,
unsafe query ids, raw policy-context values, and content-derived prompt/evidence
hashes are not persisted in the sample trace.
Trace evidence references are capped at 99 entries because the persistent schema
uses fixed two-digit `evidence_ref:NN` handles; larger runtime evidence sets fail
closed rather than emitting schema-invalid refs.
Unsupported-tool requests fail closed and emit empty trace `selected_tools`, even
when the request mixes known and unknown tool names. Runtime `tools_called`
entries are limited to unique schema-known L0-L8 runtime call names, so unknown,
repeated, or overlong runtime tool-name traces are not valid persistent traces.
Runtime fail-closed categories are also constrained to schema-known buckets;
raw path-like failure reasons collapse to `runtime_fail_closed` before
persistence.
If runtime instrumentation emits an unknown or repeated `tools_called` name, the adapter
fails closed with `runtime_tool_call_drift` and persists only schema-known call
names.
If the underlying runtime reports `runtime_contract_violation=true`, the
adapter fails closed even when the runtime also reports answer-allowed evidence,
and it does not persist raw contract guard names or raw failure paths.
If a runtime answer result returns source atoms or evidence bundles outside the
explicit candidate scope, the adapter treats the result as a runtime contract
violation and emits empty evidence refs.
If runtime invocation raises before returning a bounded result, the adapter
still emits a schema-valid `runtime_fail_closed` trace without persisting the
raw exception message or source identity.
If the caller supplies a malformed top-level source registry instead of a
bounded mapping, candidate-scope preflight fails closed before runtime tool
calls and without persisting raw registry text.
Malformed request-context payloads also fail closed before runtime invocation,
so caller-controlled raw context strings are not coerced into runtime context.

## Failure Categories

The portfolio layer uses conservative categories:

| Category | Decision |
|---|---|
| unsupported source family | fail closed |
| unsupported tool | fail closed |
| namespace mismatch | fail closed |
| production indexing scope | fail closed |
| malformed request context | fail closed |
| missing evidence for evidence-only tool | fail closed |
| candidate scope missing from registry | fail closed |
| candidate scope source-family mismatch | fail closed |
| malformed source registry | fail closed |
| runtime contract violation | fail closed |
| runtime invocation exception | fail closed |
| repeated or overlong runtime tool-call trace | fail closed |
| post-runtime candidate/evidence scope drift | fail closed |
| evidence reference count over trace schema bound | fail closed |
| insufficient evidence | fail closed |
| official request without user approval | fail closed |
| ambiguous answerability | diagnostic-only or fail closed |

## Tests / Checks

Current verification run:

| Command | Result |
|---|---|
| `python -X utf8 -m pytest ai/tests/test_agentops_portfolio_runtime_contract.py -q` | 28 passed, 1 warning |
| `python -X utf8 -m py_compile ai/app/capabilities/rag_orchestrator/agentops_runtime.py` | passed |
| `python -X utf8 -m json.tool docs/agentops_trace_schema.json` and `python -X utf8 -m json.tool reports/agentops_sample_trace.json` | passed |
| success and fail-closed trace drift guards against `docs/agentops_trace_schema.json` and `run_agentops_diagnostic(...)` | covered by `test_agentops_trace_schema_and_sample_match_runtime_contract` |
| allowed/fail-closed trace policy-boundary drift guard | covered by `test_agentops_trace_schema_rejects_policy_boundary_drift` |
| unknown runtime tool-name schema guard | covered by `test_agentops_trace_schema_rejects_unknown_runtime_tool_names` |
| safe run-id and query-id schema/runtime guard | covered by `test_agentops_context_rejects_unsafe_run_id_before_trace_emit` |
| malformed request-context guard | covered by `test_agentops_runtime_blocks_malformed_request_context_before_tool_calls` |
| runtime failure-category sanitization guard | covered by `test_agentops_trace_sanitizes_runtime_failure_category_before_persistence` |
| runtime contract-violation flag fail-closed guard | covered by `test_agentops_runtime_contract_violation_forces_fail_closed_trace` |
| runtime exception fail-closed trace guard | covered by `test_agentops_runtime_exception_fails_closed_without_raw_exception_leak` |
| evidence reference count schema-bound guard | covered by `test_agentops_trace_fails_closed_when_evidence_reference_count_exceeds_schema_bound` |
| runtime tool-call drift fail-closed guard | covered by `test_agentops_trace_fails_closed_for_unknown_runtime_tool_call_names` and `test_agentops_trace_fails_closed_for_repeated_runtime_tool_call_names` |
| post-runtime candidate/evidence scope drift guard | covered by `test_agentops_trace_fails_closed_for_post_runtime_candidate_scope_drift` |
| unsafe report artifact path leakage guard | covered by `test_agentops_trace_blocks_unsafe_report_artifact_paths` |
| invalid candidate scope pre-runtime guard, including malformed candidate records and missing candidate `source_family` metadata | covered by `test_agentops_runtime_blocks_invalid_candidate_scope_before_tool_calls` |
| malformed top-level source registry pre-runtime guard | covered by `test_agentops_runtime_blocks_malformed_source_registry_before_tool_calls` |
| portfolio/resume rendered PDF text contract | covered by `test_portfolio_and_resume_pdf_builders_render_artifact_text_contract` |
| `python -X utf8 ai/scripts/rag_eval.py current --check` | passed; `current_resolves_to=v6_9_answer_quality_gate_packet_nonprod`, official input counters remain `0`, answer/retrieval quality metrics remain false |
| `python -X utf8 -m pytest ai/tests/test_agentops_portfolio_runtime_contract.py ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py -q` | 53 passed, 8 warnings |
| `git status --short -- ai/eval/eval_queries ai/eval/source_registry ai/eval/indexes ai/eval/silver ai/eval/reports/rag-ingestion/status.jsonl` | no protected-surface changes |

Warnings were FAISS/Numpy, pydantic, requests, and pytest-asyncio environment
deprecation/configuration warnings; they did not fail the test runs.

## Role-Fit Mapping

| AI Agents Platform Engineer area | Repo artifact |
|---|---|
| Agent Runtime | `agent_runtime.py`, `agentops_runtime.py` |
| LLMOps | diagnostic report/status artifacts, answer-quality gate packet |
| Agent Control Plane | `AgentOpsPolicy`, L0-L8 `ToolRegistry`, current/rollback registry |
| Agent data connection | SearchUnit/SearchView indexes, SourceAtom registry, runtime adapters |
| quality evaluation | v6 metric-gated packets, `rag_eval.py --check`, contract tests |
| observability | run trace schema/sample, `report.json`, `status.jsonl`, progress ledgers |
| AI Coding Assistant workflow | Codex-generated tests, docs updates, progress log, verification commands |

## Implemented vs Documented

Implemented:

| Item | Artifact |
|---|---|
| AgentOps tool registry | `agentops_runtime.py` |
| policy/guardrail decisions | `AgentOpsPolicy` |
| redacted run trace creation | `AgentOpsRunTrace` |
| diagnostic runtime wrapper | `run_agentops_diagnostic` |
| tests | `ai/tests/test_agentops_portfolio_runtime_contract.py` |

Documented architecture:

| Item | Artifact |
|---|---|
| portfolio positioning | `README.md` |
| schema contract | `docs/agentops_trace_schema.json` |
| sample trace | `reports/agentops_sample_trace.json` |
| role-fit report | this file |

## Known Limitations

- No official answer-quality metric is opened in this task.
- No gold, qrels, expected answer, supporting evidence, relevance, or
  answerability labels were created or changed.
- The runtime remains non-production and diagnostic-only.
- The adapter does not add autonomous planning or unsafe code execution.
- The adapter requires explicit bounded candidate evidence scope with declared
  source-family metadata, and does not
  fall back to broad source-registry scans.
- Persistent sample traces use redacted opaque references rather than raw
  evidence, prompt logs, or content-derived hashes.
- External APIs/local LLM calls are not required for the AgentOps tests.
- Portfolio PDF builder changes are limited to the generated portfolio source
  and regenerated local PDF artifacts needed to keep trace proof text current.

## Recommended Next Steps

1. Add a default-off non-production latency/cost smoke only under explicit scope;
   this would not be live-readiness or an official metric lane.
2. Add human-review workflow only if the user explicitly opens gold/evidence or
   answerability/relevance judgments.
3. Keep portfolio language anchored to trace/report evidence rather than product
   success claims.
