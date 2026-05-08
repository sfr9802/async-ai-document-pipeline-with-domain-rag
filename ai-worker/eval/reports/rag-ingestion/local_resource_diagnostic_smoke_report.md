# Local Resource Diagnostic Smoke Report

- Status: `PASS`.
- Role: diagnostic-only local resource availability check.
- External live LLM run: `false`.
- Production index mutation: `false`.
- Official denominator registry changed: `false`.

## DB

- PostgreSQL: `PASS` - PostgreSQL reachable.
- Schemas: `PASS` - aipipeline + ragmeta schemas / tables present.

## Local LLM

- Status: `PASS`.
- Base URL: `http://localhost:8081/v1`.
- Model: `gemma4-e2b-local`.
- Models available: `1`.
