# Silver Tuning Query Delta Report

- Status: `PASS`.
- Baseline TEXT profile: `baseline_text_title_section_bm25`.
- Selected TEXT profile: `tuned_text_section_boost_bm25`.
- Selection data: `silver_only`; gold used for selection: `False`.
- Assessment: `remain_diagnostic_only`. Production-ready claimed: `false`.
- Reason: Hit@5 regressed on frozen cleaned gold; keep selected TEXT profile diagnostic-only until the lost hits are reviewed.

## Metrics

| metric | before | after | delta |
|---|---:|---:|---:|
| Hit@1 | 0.7101 | 0.7246 | 0.0145 |
| Hit@3 | 0.7971 | 0.7971 | 0.0000 |
| Hit@5 | 0.8406 | 0.8261 | -0.0145 |
| Hit@10 | 0.8696 | 0.8696 | 0.0000 |
| MRR@10 | 0.7605 | 0.7710 | 0.0105 |
| recall@10 | 0.8696 | 0.8696 | 0.0000 |

## Query Movement

- Improved: `5`.
- Regressed: `4`.
- Unchanged: `60`.
- Hit@5 lost: `1`; Hit@5 recovered: `0`.

## Regressed Queries

| query_id | bucket | before_rank | after_rank | rank_delta |
|---|---|---:|---:|---:|
| `text_namu_v2_0011` | direct_fact_lookup | 6.0000 | 8.0000 | -2.0000 |
| `text_namu_v2_0021` | section_level_summary | 4.0000 | 5.0000 | -1.0000 |
| `text_namu_v2_0028` | scene_quote_description_recall | 1.0000 | 2.0000 | -1.0000 |
| `text_namu_v2_0058` | direct_fact_lookup | 5.0000 | 6.0000 | -1.0000 |

## Improved Queries

| query_id | bucket | before_rank | after_rank | rank_delta |
|---|---|---:|---:|---:|
| `text_namu_v2_0018` | section_level_summary | 2.0000 | 1.0000 | 1.0000 |
| `text_namu_v2_0031` | scene_quote_description_recall | 3.0000 | 2.0000 | 1.0000 |
| `text_namu_v2_0053` | direct_fact_lookup | 3.0000 | 2.0000 | 1.0000 |
| `text_namu_v2_0059` | direct_fact_lookup | 2.0000 | 1.0000 | 1.0000 |
| `text_namu_v2_0076` | scene_quote_description_recall | 9.0000 | 8.0000 | 1.0000 |

## Abstain And Hard Negatives

- Abstain diagnostic expected Hit@10: `0.5000` -> `0.6000`.
- Hard negative confusion rate: `0.0110` -> `0.0110`.
