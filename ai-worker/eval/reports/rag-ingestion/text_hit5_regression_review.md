# TEXT Hit@5 Regression Review

- Status: `PASS`.
- Selected TEXT profile assessment: `remain_diagnostic_only`.
- Promotion candidate: `false`.
- Reason: At least one frozen cleaned gold query lost Hit@5 after silver-only profile selection.

## Hit@5 Summary

- Lost Hit@5: `1`.
- Recovered Hit@5: `0`.
- Stable Hit@5: `57`.
- Stable misses: `11`.
- Net Hit@5 delta count: `-1`.

## Lost Hit@5 Queries

| query_id | bucket | before_rank | after_rank | rank_delta |
|---|---|---:|---:|---:|
| `text_namu_v2_0058` | direct_fact_lookup | 5.0000 | 6.0000 | -1.0000 |

## Recovered Hit@5 Queries

- None.
