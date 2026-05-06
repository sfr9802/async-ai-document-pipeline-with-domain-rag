# PDF/XLSX Answer Intent Prompt Contract

Status: diagnostic contract draft. This is not promotion evidence.

## Scope

This contract applies to PDF and XLSX answer generation after retrieval/context
assembly. Retrieval is allowed to find keywords, pages, cells, ranges, bboxes,
sheets, or sections. The answer, however, must satisfy the user's content
intent, not merely echo the retrieval anchor.

This contract is diagnostic-only for the current review. It does not change
gold policy, denominators, candidate artifacts, SearchUnit behavior, parser
coverage, thresholds, reranking, or promotion status.

## Intent First

Before answering, classify the query internally by the content it asks for.
Korean lookup verbs such as `찾아줘`, `어디야`, `확인해줘`, and `알려줘` are
content-seeking intents. They do not mean "return the matched keyword only" and
they do not mean "return only sheet/range/page/bbox metadata."

The retrieved keyword or location is only evidence discovery. The answer target
is the sentence, table row, column, value, section, or local context that makes
the keyword relevant to the question.

## Answer Shape Enum

- `LOCATION_PLUS_CONTENT`: give a concise locator and the content at that
  locator.
- `TABLE_ROW_VALUE`: answer with the relevant row/column meaning and target
  value, including enough header context to understand the value.
- `TABLE_COLUMN_OR_RANGE_WITH_CONTEXT`: identify the table/range and summarize
  what the relevant column, range, or row group represents.
- `PDF_SECTION_WITH_SUMMARY`: identify the PDF page/section/paragraph and state
  what the relevant sentence, paragraph, or section says.
- `PDF_TABLE_VALUE_WITH_CONTEXT`: answer with the relevant PDF table value plus
  row label, column label, unit, and page/section context when available.
- `YES_NO_WITH_EVIDENCE`: answer yes/no first, then give the supporting content
  and citation.
- `EVIDENCE_LOCATOR_WITH_CONTENT`: provide the locator and the matching content
  claim together.
- `KEYWORD_ECHO_FORBIDDEN`: diagnostic failure state for answers that only
  repeat the query keyword, matched token, cell/range, page, bbox, sheet, or
  section without content.
- `NOT_ANSWERABLE_OR_POLICY_PENDING`: abstain or block when user review,
  evidence semantics, hidden-content policy, parser/chunk policy, or actual
  answer output is missing.

## XLSX Rules

An XLSX answer must not return only `sheet`, `range`, `cell`, or a matched
keyword. It must include the related content:

1. For table value questions, state the row identity, column meaning, value, and
   sheet/range evidence.
2. For row or range lookup questions, state what the row/range contains and why
   it is relevant, not just the address.
3. For formula/date/number-format questions, preserve the visible value,
   formula or formatting meaning, and neighboring headers needed to interpret
   the value.
4. For hidden sheet/column probes, do not surface hidden content as an answer.
   If policy blocks the row, mark it as policy-pending or not answerable.
5. A range-level retrieval hit can support answer generation only if the answer
   names the content target inside that range.

## PDF Rules

A PDF answer must not return only `page`, `bbox`, `section`, or a matched
keyword. It must briefly answer what the cited sentence, table, paragraph, or
section says:

1. For sentence/paragraph questions, summarize the relevant claim in one short
   answer and attach the page/bbox citation to that claim.
2. For PDF table questions, state the row label, column label, value, unit, and
   table/page context when available.
3. For page or section lookup questions, include both the locator and the
   content found there.
4. If PDF C7 policy is unresolved, keep the row diagnostic-only and do not infer
   a gold-policy decision.

## Citation Rules

Citations attach to the claim/content that answers the user's intent. A citation
to the place where a keyword appears is insufficient if the cited content does
not support the answer claim.

The following must be counted as failures when actual answer output exists:

- keyword-only answers
- sheet/range/cell-only XLSX answers
- page/bbox/section-only PDF answers
- citations attached only to a keyword occurrence instead of the answered claim
- grounded answers that answer a different intent from the query

## Diagnostic Gate

Dry-run extractive previews are not actual answer output. If only dry-run
previews exist, answer-shape metric values remain blocked/null.

A local LLM diagnostic run may produce actual answer output for shape analysis,
but it is still diagnostic evidence only. In that case metric values may be
populated, while XLSX answer/E2E denominator remains `0`, PDF answer denominator
remains `0`, and R8/citation support remains blocked until answer-shape
alignment is explicitly accepted for a future answer-quality lane.

If the local output contains invalid JSON, keyword echo, locator-only answers,
or claim/citation shape failures, the report status must describe diagnostic
shape failure rather than a promotion or quality pass.
