# official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage Triage Delta

Diagnostic-only delta for the remaining TEXT locator residual.

- TEXT locator missing: `1` -> `0`
- LLM-generated locator missing failures: `1` -> `0`
- TEXT locator byte-equal after: `True`
- TEXT locator normalized-equal after: `True`

| Query ID | Before lane B | After lane B | Text locator present | Byte equal | Normalized equal |
|---|---|---|---:|---:|---:|
| `text_namu_v2_0012` | `CITATION_PAYLOAD_SCHEMA_MISMATCH` | `LLM_EXPECTED_SPAN_MISMATCH` | `True` | `True` | `True` |
