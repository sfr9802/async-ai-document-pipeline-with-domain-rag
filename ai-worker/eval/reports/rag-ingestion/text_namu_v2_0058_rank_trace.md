# text_namu_v2_0058 Rank Trace

- Status: `PASS`.
- Query: `원피스 팬 레터는 어떤 원작과 기념 성격을 가진 애니야`.
- Baseline profile: `baseline_text_title_section_bm25`.
- Tuned profile: `tuned_text_section_boost_bm25`.
- Expected rank: `5` -> `6`.
- Hit@5: `true` -> `false`.
- Root cause: `section_boost_displaced_borderline_hit5`.
- Recommendation: Keep tuned_text_section_boost_bm25 diagnostic-only. Review a capped or query-bucket-gated section boost and add this query to the Hit@5 regression watchlist before any promotion review.

## Score Availability

- The local deterministic TextIndex emits final BM25 scores only. Field contribution is represented by configured weights plus token-overlap diagnostics.

## Tuned Top 5 Displacing Candidates

| rank | score | expected | doc_id | chunk_id | title | section_overlap | chunk_overlap |
|---:|---:|---|---|---|---|---|---|
| 1 | 19.2460 | `false` | `bb6462dace081f88` | `11eacfc71fbfba70` | 원피스 필름 레드 |  | 팬 |
| 2 | 16.1638 | `false` | `1304f44478650c7a` | `3a951d536a6d2b70` | 원피스(애니메이션)/OST |  | 가진 |
| 3 | 15.6927 | `false` | `66157f97d902e013` | `6702f07e3d94fdf2` | 일일외출록 반장 / 줄거리 | 원피스 | 가진 |
| 4 | 15.6904 | `false` | `f4fbe985489fa342` | `b298ed3116934faf` | 원피스(애니메이션) |  | 원작과 |
| 5 | 15.3768 | `false` | `88f920d4da21fbfc` | `b14d3ee1aca8fa9f` | 사랑하는 원피스(애니메이션) |  | 가진, 원피스 |

## Baseline Top 10

| rank | score | expected | doc_id | chunk_id | title | section_overlap | chunk_overlap |
|---:|---:|---|---|---|---|---|---|
| 1 | 19.3392 | `false` | `bb6462dace081f88` | `11eacfc71fbfba70` | 원피스 필름 레드 |  | 팬 |
| 2 | 16.1442 | `false` | `1304f44478650c7a` | `3a951d536a6d2b70` | 원피스(애니메이션)/OST |  | 가진 |
| 3 | 15.5898 | `false` | `f4fbe985489fa342` | `b298ed3116934faf` | 원피스(애니메이션) |  | 원작과 |
| 4 | 15.3059 | `false` | `88f920d4da21fbfc` | `b14d3ee1aca8fa9f` | 사랑하는 원피스(애니메이션) |  | 가진, 원피스 |
| 5 | 15.1795 | `true` | `579e66394c3ce1be` | `ba8965f5b1a53178` | ONE PIECE FAN LETTER |  | 기념, 원피스 |
| 6 | 14.6210 | `false` | `08002c3a3fa1ff97` | `75cf8b641f07b7a1` | 원피스 필름 레드/사운드트랙 |  | 팬 |
| 7 | 14.4074 | `false` | `00c3bcca2fd178d1` | `44472d2c91828b62` | 원피스(애니메이션)/회차 목록/1~516화 |  | 어떤 |
| 8 | 14.3449 | `false` | `f4fbe985489fa342` | `4cb52c0780fb3e98` | 원피스(애니메이션) |  | 원작과 |
| 9 | 14.3268 | `false` | `66157f97d902e013` | `6702f07e3d94fdf2` | 일일외출록 반장 / 줄거리 | 원피스 | 가진 |
| 10 | 14.2226 | `false` | `09a387e0872a69d1` | `1eb7ab7142df61c7` | 그리드맨 유니버스 / 등장인물 |  | 가진, 어떤, 팬 |

## Tuned Top 10

| rank | score | expected | doc_id | chunk_id | title | section_overlap | chunk_overlap |
|---:|---:|---|---|---|---|---|---|
| 1 | 19.2460 | `false` | `bb6462dace081f88` | `11eacfc71fbfba70` | 원피스 필름 레드 |  | 팬 |
| 2 | 16.1638 | `false` | `1304f44478650c7a` | `3a951d536a6d2b70` | 원피스(애니메이션)/OST |  | 가진 |
| 3 | 15.6927 | `false` | `66157f97d902e013` | `6702f07e3d94fdf2` | 일일외출록 반장 / 줄거리 | 원피스 | 가진 |
| 4 | 15.6904 | `false` | `f4fbe985489fa342` | `b298ed3116934faf` | 원피스(애니메이션) |  | 원작과 |
| 5 | 15.3768 | `false` | `88f920d4da21fbfc` | `b14d3ee1aca8fa9f` | 사랑하는 원피스(애니메이션) |  | 가진, 원피스 |
| 6 | 15.2518 | `true` | `579e66394c3ce1be` | `ba8965f5b1a53178` | ONE PIECE FAN LETTER |  | 기념, 원피스 |
| 7 | 15.0529 | `false` | `78ad18e41432c62a` | `6abcb3a87e051387` | 공포의 물고기 | 원작과 | 어떤 |
| 8 | 15.0323 | `false` | `66157f97d902e013` | `4869d1727c5ee436` | 일일외출록 반장 / 줄거리 | 원피스 | 어떤 |
| 9 | 14.6560 | `false` | `08002c3a3fa1ff97` | `75cf8b641f07b7a1` | 원피스 필름 레드/사운드트랙 |  | 팬 |
| 10 | 14.3561 | `false` | `f4fbe985489fa342` | `4cb52c0780fb3e98` | 원피스(애니메이션) |  | 원작과 |
