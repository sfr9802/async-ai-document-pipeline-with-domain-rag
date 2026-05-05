# R8 — B5-namu Citation Support / Grounding

## Goal

LLM answer의 claim이 retrieved context에 의해 support되는지 확인한다.

## New Files

```text
scripts/rag_text_namu_v4_citation_support.py
ai-worker/tests/test_rag_text_namu_v4_citation_support.py
reports/rag_text_namu_v4_citation_support_report.json
```

## Checks

```text
1. answer cites retrieved chunk ids only
2. cited chunk text contains supporting evidence
3. unsupported claims are counted
4. citation coverage is measured at claim level
5. abstain rows do not require supporting citations
```

## Metrics

```text
citation_support_rate
claim_support_rate
unsupported_claim_count
missing_citation_count
citation_not_in_retrieved_context_count
abstain_citation_violation_count
```

## Acceptance Criteria

- Answer eval report exists.
- Citation support is not inferred from retrieval hit alone.
- Unsupported claims are visible in report.
