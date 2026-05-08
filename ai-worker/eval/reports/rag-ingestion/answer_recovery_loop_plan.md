# Answer Recovery Loop Plan

- Status: `diagnostic_runtime_bridge_only`.
- Reused loop: `app.capabilities.agent.loop.AgentLoopController` through `AgenticRetrievalLoopAdapter`.
- Max iterations: `2`; max query rewrites: `3`.
- Production index mutation: `false`; broad indexing: `false`; official denominator mutation: `false`.
- TEXT: allow query rewrite, title/entity disambiguation, section expansion, adjacent chunk expansion; keep `tuned_text_section_boost_bm25` diagnostic-only.
- XLSX: use only strict wrapper context; preserve parser_version, location_json, citation_text; hidden content cannot surface.
- PDF CONTENT: prefer native PDF text; OCR fallback is lower-trust diagnostic metadata; report native/OCR conflicts.
- PDF FILE LOOKUP: file identity only; no content, page, bbox, table, row, column, or value success claims.
- OCR/IDP/multimodal: diagnostic hints and retrieval expansion only; cannot make official support by default.
