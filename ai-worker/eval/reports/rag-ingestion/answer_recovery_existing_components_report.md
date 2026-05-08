# Answer Recovery Existing Components Report

- Status: `PASS`.
- Production index mutation: `false`.
- Broad indexing: `false`.
- Official denominator registry changed: `false`.

## Reuse Decision

- Agentic loop component: `app.capabilities.agent.loop.AgentLoopController`.
- New code is limited to the sufficiency judge, policy router, loop adapter, and report-only harness.

## Discovered Components

| module | status | symbols |
|---|---|---|
| `app.capabilities.agent.loop` | `FOUND` | `AgentLoopController, LoopBudget, LoopOutcome, ExecuteFn` |
| `app.capabilities.agent.graph_loop.adapters` | `FOUND` | `AgentLoopGraph` |
| `app.capabilities.agent.critic` | `FOUND` | `RuleCritic, LlmCritic, CritiqueResult` |
| `app.capabilities.agent.rewriter` | `FOUND` | `NoOpQueryRewriter, LlmQueryRewriter, QueryRewriterProvider` |
| `app.capabilities.rag.query_parser` | `FOUND` | `RegexQueryParser, LlmQueryParser, ParsedQuery` |
| `app.capabilities.rag.generation` | `FOUND` | `ExtractiveGenerator, RetrievedChunk` |
| `app.capabilities.rag_orchestrator.evidence` | `FOUND` | `Evidence, QueryPolicy` |
| `app.capabilities.rag_orchestrator.citation_verify` | `FOUND` | `citation_verify_tool, verify_evidence` |
| `app.capabilities.rag_orchestrator.evidence_merge` | `FOUND` | `evidence_merge_tool` |
| `app.capabilities.rag_orchestrator.answer_policy` | `FOUND` | `prepare_answer_handoff, build_no_evidence_response` |
| `eval.harness.pdf_xlsx_answer_evidence_serializer` | `FOUND` | `serialize_input_row, serialize_input_rows` |
| `eval.harness.pdf_xlsx_deterministic_answer_compiler` | `FOUND` | `compile_evidence_row, compile_evidence_rows` |

## Risk Notes

- Do not promote answer denominators from this diagnostic bridge.
- Do not use PDF FILE lookup as content evidence.
- Do not expose hidden XLSX content.
- OCR, IDP, and multimodal evidence remains diagnostic-only by default.
- Local LLM smoke output is diagnostic-only and not promotion evidence.
