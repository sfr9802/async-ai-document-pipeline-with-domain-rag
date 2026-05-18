# official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement Actual Response Audit

This audit is diagnostic-only. Expected answers and supporting evidence are intentionally not printed here.

## gq_auto_010 (PDF)

- Query: 2월 실업률은 전년 같은 달보다 어떻게 변했나요?
- Lane A answer: **Query:** 2월 실업률은 전년 같은 달보다 어떻게 변했나요?

**Short answer:** ▪ 실업률은 모든 연령계층에서 상승 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.

**Supporting passages:**
1. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.487) ▪ 실업률은 모든 연령계층에서 상승 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf page 8: ▪ 실업률은 모든 연령계층에서 상승 | paragraph_text)
2. [docv_8b23a58c27c5518a#pdf_business_ocr_mm] (score=0.436) 수 출(FOB) | 수 입(CIF) | 수출입차 | 금 액 | 증가율 | 2022 | 6,835.8 | 6.1 | 7,313.7 | 18.9 | △477.8 | 2023 | 6,322.3 | △7.5 | 6,425.7 | △12.1 | △103.5 | 2024 | 6,836.1 | 8.1 | 6,317.7 | △1.7 | 518.4 | 2022.Ⅳ | 1,590.5 | △10.0 | 1,776.4 | 3.1 | △185.9 | 2023.Ⅰ | 1,512.2 | △12.8 | 1,740.2 | △2.2 | △227.9 (local-storage/2cfd4aa2-8956-4f0b-9719-731002d2c767/input_file/492ca671-e252-45a1-998d-f9a095855b82-2025_...
3. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.430) 광공업 생산, 서비스업 생산, 건설투자는 감소 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf page 5: 광공업 생산, 서비스업 생산, 건설투자는 감소 | paragraph_text)
4. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.413) 마. 주요국가의 환율변동 비교 | 일본(￥/달러) 4 ｣ | 대만(NT달러/달러) 4 | 한국(원/달러) | 유로(달러/EUR) | 2018 | 1,118.1 | △4.18 | 1,100.30 | 110.36 | 2.29 | 30.57 | △2.45 | 1.1441 | △4.18 | 2019 | 1,157.8 | △3.43 | 1,165.65 | 108.87 | 1.36 | 30.09 | 1.59 | 1.1206 | △2.05 | 2020 | 1,088.0 | 6.42 | 1,180.1 | 103.20 | 5.49 | 28.13 | 6.97 | 1.2300 | 9.76 | 2019.Ⅱ | 1,156.8 | △3.35 | 1,165.91 | 107.78 | 2.39 | 30.97 | △1.30 | 1.1...

**Sources:** docv_8b23a58c27c5518a, docv_fe2470815512a395
- Lane B answer: 2월 실업률은 전년 같은 달보다 상승했습니다.
- Lane C answer: 2월 실업률은 전년 같은 달보다 상승했습니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "PDF_BBOX_LOCATOR_LOSS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"], "live_llm_retrieval_topk": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"], "v3_primary_replay": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "64360248-5d63-43bb-a9b2-5dedbea3df84", "7bf516bf-2a17-4303-86d8-3cffaa04846e", "f5815847-706b-4fb1-bc99-f2a3284c5ede"]}`
- Locator fields: `{"bbox": [63.65, 121.56, 227.84, 131.77], "document_version_id": "docv_fe2470815512a395", "page": 8, "physical_page_index": 7, "region_type": "paragraph", "row_label": "▪ 실업률은 모든 연령계층에서 상승", "search_unit_id": "7bf516bf-2a17-4303-86d8-3cffaa04846e", "source_pdf_path": "local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf", "target_column": "paragraph_text"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "live_llm_retrieval_topk": {"category": "PDF_BBOX_LOCATOR_LOSS", "cited_search_unit_ids": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {"7bf516bf-2a17-4303-86d8-3cffaa04846e": ["source_pdf_path"]}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": false, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "64360248-5d63-43bb-a9b2-5dedbea3df84", "7bf516bf-2a17-4303-86d8-3cffaa04846e", "f5815847-706b-4fb1-bc99-f2a3284c5ede"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:PDF_BBOX_LOCATOR_LOSS, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `repair_pdf_locator_preservation`

## gq_auto_024 (PDF)

- Query: 1월 산업활동에서 생산 지표는 어떻게 움직였나요?
- Lane A answer: **Query:** 1월 산업활동에서 생산 지표는 어떻게 움직였나요?

**Short answer:** 광공업 생산, 서비스업 생산, 건설투자는 감소 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.

**Supporting passages:**
1. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.512) 광공업 생산, 서비스업 생산, 건설투자는 감소 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf page 5: 광공업 생산, 서비스업 생산, 건설투자는 감소 | paragraph_text)
2. [docv_8b23a58c27c5518a#pdf_business_ocr_mm] (score=0.473) 수 출(FOB) | 수 입(CIF) | 수출입차 | 금 액 | 증가율 | 2022 | 6,835.8 | 6.1 | 7,313.7 | 18.9 | △477.8 | 2023 | 6,322.3 | △7.5 | 6,425.7 | △12.1 | △103.5 | 2024 | 6,836.1 | 8.1 | 6,317.7 | △1.7 | 518.4 | 2022.Ⅳ | 1,590.5 | △10.0 | 1,776.4 | 3.1 | △185.9 | 2023.Ⅰ | 1,512.2 | △12.8 | 1,740.2 | △2.2 | △227.9 (local-storage/2cfd4aa2-8956-4f0b-9719-731002d2c767/input_file/492ca671-e252-45a1-998d-f9a095855b82-2025_...
3. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.419) ▪ 실업률은 모든 연령계층에서 상승 (local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf page 8: ▪ 실업률은 모든 연령계층에서 상승 | paragraph_text)
4. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.402) 마. 주요국가의 환율변동 비교 | 일본(￥/달러) 4 ｣ | 대만(NT달러/달러) 4 | 한국(원/달러) | 유로(달러/EUR) | 2018 | 1,118.1 | △4.18 | 1,100.30 | 110.36 | 2.29 | 30.57 | △2.45 | 1.1441 | △4.18 | 2019 | 1,157.8 | △3.43 | 1,165.65 | 108.87 | 1.36 | 30.09 | 1.59 | 1.1206 | △2.05 | 2020 | 1,088.0 | 6.42 | 1,180.1 | 103.20 | 5.49 | 28.13 | 6.97 | 1.2300 | 9.76 | 2019.Ⅱ | 1,156.8 | △3.35 | 1,165.91 | 107.78 | 2.39 | 30.97 | △1.30 | 1.1...

**Sources:** docv_8b23a58c27c5518a, docv_fe2470815512a395
- Lane B answer: 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다.
- Lane C answer: 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["64360248-5d63-43bb-a9b2-5dedbea3df84"], "live_llm_retrieval_topk": ["64360248-5d63-43bb-a9b2-5dedbea3df84"], "v3_primary_replay": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "64360248-5d63-43bb-a9b2-5dedbea3df84", "7bf516bf-2a17-4303-86d8-3cffaa04846e", "f5815847-706b-4fb1-bc99-f2a3284c5ede"]}`
- Locator fields: `{"bbox": [82.35, 150.44, 313.91, 162.17], "document_version_id": "docv_fe2470815512a395", "page": 5, "physical_page_index": 4, "region_type": "paragraph", "row_label": "광공업 생산, 서비스업 생산, 건설투자는 감소", "search_unit_id": "64360248-5d63-43bb-a9b2-5dedbea3df84", "source_pdf_path": "local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf", "target_column": "paragraph_text"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["64360248-5d63-43bb-a9b2-5dedbea3df84"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["64360248-5d63-43bb-a9b2-5dedbea3df84"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "64360248-5d63-43bb-a9b2-5dedbea3df84", "7bf516bf-2a17-4303-86d8-3cffaa04846e", "f5815847-706b-4fb1-bc99-f2a3284c5ede"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_030 (PDF)

- Query: 2020년 한국 원달러 기말 환율은 얼마인가요?
- Lane A answer: **Query:** 2020년 한국 원달러 기말 환율은 얼마인가요?

**Short answer:** 마.

**Supporting passages:**
1. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.682) 마. 주요국가의 환율변동 비교 | 일본(￥/달러) 4 ｣ | 대만(NT달러/달러) 4 | 한국(원/달러) | 유로(달러/EUR) | 2018 | 1,118.1 | △4.18 | 1,100.30 | 110.36 | 2.29 | 30.57 | △2.45 | 1.1441 | △4.18 | 2019 | 1,157.8 | △3.43 | 1,165.65 | 108.87 | 1.36 | 30.09 | 1.59 | 1.1206 | △2.05 | 2020 | 1,088.0 | 6.42 | 1,180.1 | 103.20 | 5.49 | 28.13 | 6.97 | 1.2300 | 9.76 | 2019.Ⅱ | 1,156.8 | △3.35 | 1,165.91 | 107.78 | 2.39 | 30.97 | △1.30 | 1.1...
2. [docv_8b23a58c27c5518a#pdf_business_ocr_mm] (score=0.509) 수 출(FOB) | 수 입(CIF) | 수출입차 | 금 액 | 증가율 | 2022 | 6,835.8 | 6.1 | 7,313.7 | 18.9 | △477.8 | 2023 | 6,322.3 | △7.5 | 6,425.7 | △12.1 | △103.5 | 2024 | 6,836.1 | 8.1 | 6,317.7 | △1.7 | 518.4 | 2022.Ⅳ | 1,590.5 | △10.0 | 1,776.4 | 3.1 | △185.9 | 2023.Ⅰ | 1,512.2 | △12.8 | 1,740.2 | △2.2 | △227.9 (local-storage/2cfd4aa2-8956-4f0b-9719-731002d2c767/input_file/492ca671-e252-45a1-998d-f9a095855b82-2025_...

**Sources:** docv_8b23a58c27c5518a, docv_fe2470815512a395
- Lane B answer: 2020년 한국 원달러 기말 환율은 1,088.0원/달러입니다.
- Lane C answer: 2020년 한국 원달러 기말 환율은 1,088.0원/달러입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9"], "live_llm_retrieval_topk": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9"], "v3_primary_replay": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "f5815847-706b-4fb1-bc99-f2a3284c5ede"]}`
- Locator fields: `{"bbox": [73.6, 76.45, 239.27, 88.44], "document_version_id": "docv_fe2470815512a395", "page": 65, "physical_page_index": 64, "region_type": "table_body", "row_label": "마. 주요국가의 환율변동 비교", "search_unit_id": "0facad40-0431-4e90-ae9b-5d47c4cfbde9", "source_pdf_path": "local-storage/276e2d37-7c54-4d23-8d52-1a2c5a7ea1d9/input_file/9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf", "target_column": "일본(￥/달러) 4 ｣ | 대만(NT달러/달러) 4 | 한국(원/달러) | 유로(달러/EUR)"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "f5815847-706b-4fb1-bc99-f2a3284c5ede"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_pdf_section_question_001 (PDF)

- Query: 2024년 수출입차 금액은 얼마인가요?
- Lane A answer: **Query:** 2024년 수출입차 금액은 얼마인가요?

**Short answer:** 수 출(FOB) | 수 입(CIF) | 수출입차 | 금 액 | 증가율 | 2022 | 6,835.

**Supporting passages:**
1. [docv_8b23a58c27c5518a#pdf_business_ocr_mm] (score=0.603) 수 출(FOB) | 수 입(CIF) | 수출입차 | 금 액 | 증가율 | 2022 | 6,835.8 | 6.1 | 7,313.7 | 18.9 | △477.8 | 2023 | 6,322.3 | △7.5 | 6,425.7 | △12.1 | △103.5 | 2024 | 6,836.1 | 8.1 | 6,317.7 | △1.7 | 518.4 | 2022.Ⅳ | 1,590.5 | △10.0 | 1,776.4 | 3.1 | △185.9 | 2023.Ⅰ | 1,512.2 | △12.8 | 1,740.2 | △2.2 | △227.9 (local-storage/2cfd4aa2-8956-4f0b-9719-731002d2c767/input_file/492ca671-e252-45a1-998d-f9a095855b82-2025_...
2. [docv_fe2470815512a395#pdf_business_ocr_mm] (score=0.388) 마. 주요국가의 환율변동 비교 | 일본(￥/달러) 4 ｣ | 대만(NT달러/달러) 4 | 한국(원/달러) | 유로(달러/EUR) | 2018 | 1,118.1 | △4.18 | 1,100.30 | 110.36 | 2.29 | 30.57 | △2.45 | 1.1441 | △4.18 | 2019 | 1,157.8 | △3.43 | 1,165.65 | 108.87 | 1.36 | 30.09 | 1.59 | 1.1206 | △2.05 | 2020 | 1,088.0 | 6.42 | 1,180.1 | 103.20 | 5.49 | 28.13 | 6.97 | 1.2300 | 9.76 | 2019.Ⅱ | 1,156.8 | △3.35 | 1,165.91 | 107.78 | 2.39 | 30.97 | △1.30 | 1.1...

**Sources:** docv_8b23a58c27c5518a, docv_fe2470815512a395
- Lane B answer: 
- Lane C answer: 2024년 수출입차 금액은 6,836.1입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 0.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_STRICT_JSON_PARSE_FAILURE", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["f5815847-706b-4fb1-bc99-f2a3284c5ede"], "live_llm_retrieval_topk": [], "v3_primary_replay": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "f5815847-706b-4fb1-bc99-f2a3284c5ede"]}`
- Locator fields: `{"bbox": [76.68, 103.92, 483.52, 672.6], "document_version_id": "docv_8b23a58c27c5518a", "page": 61, "physical_page_index": 60, "region_type": "table_body", "row_label": "수 출(FOB)", "search_unit_id": "f5815847-706b-4fb1-bc99-f2a3284c5ede", "source_pdf_path": "local-storage/2cfd4aa2-8956-4f0b-9719-731002d2c767/input_file/492ca671-e252-45a1-998d-f9a095855b82-2025_12_recent_economic_trends.pdf", "target_column": "수 입(CIF) | 수출입차 | 금 액 | 증가율"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["f5815847-706b-4fb1-bc99-f2a3284c5ede"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "live_llm_retrieval_topk": {"category": "LLM_STRICT_JSON_PARSE_FAILURE", "cited_search_unit_ids": [], "generated_by_llm": true, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": false, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["0facad40-0431-4e90-ae9b-5d47c4cfbde9", "f5815847-706b-4fb1-bc99-f2a3284c5ede"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id"], "source_family": "PDF"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:LLM_STRICT_JSON_PARSE_FAILURE, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `inspect_prompt_and_strict_json_response`

## text_namu_v2_0005 (TEXT)

- Query: 자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어
- Lane A answer: 자동판매기 미궁 방랑 애니 3기는 2026년 4월에 방영될 예정입니다.
- Lane B answer: 자동판매기로 다시 태어난 나는 미궁을 방랑한다(애니메이션 3기)는 2026년 4월에 방영될 예정입니다.
- Lane C answer: 자동판매기로 다시 태어난 나는 미궁을 방랑한다(애니메이션 3기)는 2026년 4월에 방영되었습니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_f078ba15a269ab6c3613f86a92c87287"], "live_llm_retrieval_topk": ["su_f078ba15a269ab6c3613f86a92c87287"], "v3_primary_replay": ["su_f078ba15a269ab6c3613f86a92c87287"]}`
- Locator fields: `{"document_id": "4fb4c291efb8b088", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_f078ba15a269ab6c3613f86a92c87287", "text_locator": {"chunk_id": "a648c3a062d55aa3", "line_number": 90724, "section_id": "6f578a505af74613", "section_path": ["개요"], "section_type": "summary", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "자동판매기로 다시 태어난 나는 미궁을 방랑한다(애니메이션 3기)"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_f078ba15a269ab6c3613f86a92c87287"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_f078ba15a269ab6c3613f86a92c87287"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_f078ba15a269ab6c3613f86a92c87287"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## text_namu_v2_0012 (TEXT)

- Query: 유우야키의 나이와 생일은 어떻게 적혀 있어
- Lane A answer: 유우야키의 나이는 16세이며, 생일은 9월 29일입니다.
- Lane B answer: 
- Lane C answer: 유우야키의 나이는 16세이며, 생일은 9월 29일입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 0.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_STRICT_JSON_PARSE_FAILURE", "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_06f074cdb73bdab41debb6167be08880"], "live_llm_retrieval_topk": [], "v3_primary_replay": ["su_06f074cdb73bdab41debb6167be08880"]}`
- Locator fields: `{"document_id": "474e24d5441aeacd", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_06f074cdb73bdab41debb6167be08880", "text_locator": {"chunk_id": "4977eb3ffeb4cf67", "line_number": 110673, "section_id": "dac284755f8094ee", "section_path": ["토오노텐구닌자단", "유우야키"], "section_type": "character", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "등장인물/NewWave"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_06f074cdb73bdab41debb6167be08880"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": "LLM_STRICT_JSON_PARSE_FAILURE", "cited_search_unit_ids": [], "generated_by_llm": true, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": false, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_06f074cdb73bdab41debb6167be08880"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: failing lanes require row-level triage: v3_primary_replay:LLM_TRUE_PARTIAL_SYNTHESIS, live_llm_retrieval_topk:LLM_STRICT_JSON_PARSE_FAILURE, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `inspect_prompt_and_strict_json_response`

## text_namu_v2_0014 (TEXT)

- Query: 엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와
- Lane A answer: 엑스맨 97 등장인물 목록에서 애드버서리는 앨리슨 실리스미스이다.
- Lane B answer: 엑스맨 97(애니메이션 1기)에 등장하는 인물 목록은 다음과 같습니다:

*   애드버서리: 앨리슨 실리스미스 (카메오), 썬더볼트 로스 (마이클 맥길), 빅터 폰 둠 / 닥터 둠 (로스 마퀀드), 헬무트 제모 (라마 밸러리), 피터 파커 / 스파이더맨 (하라다 켄이치로 / 실버 사무라이), 아르카디 로소비치 / 오메가 레드 (토니 스타크 / 아이언맨), 맷 머독 / 데어데블 (닥터 스티븐 스트레인지), 트차카 / 블랙 팬서 (아이작 로빈슨스미스), 타이론 존슨 / 클록 (탠디 보언 / 대거), 메리 제인 왓슨 (엔 사바흐 누르 / 아포칼립스), 아데토쿰보 매코맥 (엔 사바흐 누르), 로스 마퀀드 (아포칼립스).
- Lane C answer: 엑스맨 97(애니메이션 1기)에 등장하는 인물 목록은 다음과 같습니다: 애드버서리 - 앨리슨 실리스미스 (카메오), 썬더볼트 로스 - 마이클 맥길, 빅터 폰 둠 / 닥터 둠 - 로스 마퀀드, 헬무트 제모 - 라마 밸러리, 피터 파커 / 스파이더맨 - 하라다 켄이치로 / 실버 사무라이, 아르카디 로소비치 / 오메가 레드 - 토니 스타크 / 아이언맨, 맷 머독 / 데어데블 - 닥터 스티븐 스트레인지, 트차카 / 블랙 팬서 - 아이작 로빈슨스미스, 타이론 존슨 / 클록 - 탠디 보언, 메리 제인 왓슨, 엔 사바흐 누르 / 아포칼립스, 아데토쿰보 매코맥 (엔 사바흐 누르), 로스 마퀀드 (아포칼립스).
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_47ded21867e4af7502f907c61048928e"], "live_llm_retrieval_topk": ["su_47ded21867e4af7502f907c61048928e"], "v3_primary_replay": ["su_47ded21867e4af7502f907c61048928e"]}`
- Locator fields: `{"document_id": "ffa9998ff6067ea2", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_47ded21867e4af7502f907c61048928e", "text_locator": {"chunk_id": "98f5315b62c0282c", "line_number": 79570, "section_id": "5539e9167b496cdc", "section_path": ["등장인물"], "section_type": "character", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "엑스맨 '97(애니메이션 1기)"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_47ded21867e4af7502f907c61048928e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_47ded21867e4af7502f907c61048928e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_47ded21867e4af7502f907c61048928e"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: failing lanes require row-level triage: v3_primary_replay:LLM_TRUE_PARTIAL_SYNTHESIS, live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `prompt_answer_renderer_triage`

## text_namu_v2_0017 (TEXT)

- Query: 실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해
- Lane A answer: 실크 고양이 가족에 대한 설명은 소년과 소녀로 나뉘어 설명됩니다. 소년(Toby, Samuel)은 유럽판에서 상냥하고 배려심이 넘치며, 집에서 배운 춤을 공연합니다. 소녀(Tiffany, Susie)는 패션 디자이너를 꿈꾸며 스케치북에 디자인을 가득 채웁니다. (출처 [1])
- Lane B answer: 실크 고양이 가족에는 소년(Toby, Samuel)과 소녀(Tiffany, Susie)가 있으며, 이들은 각기 다른 성격과 배경을 가지고 있습니다. 소년은 유럽판에서 상냥하고 배려심이 넘치며, 춤 공연을 좋아하고, 북미판에서는 테니스를 즐깁니다. 소녀는 패션 디자이너를 꿈꾸며, 자신의 스케치북을 통해 디자인을 표현하고 친구들이 자신의 옷을 입기를 기대합니다. 가족 구성원 간의 관계는 각기 다른 면모를 보입니다.
- Lane C answer: 실바니안 실크 고양이 가족에 대한 구체적인 성격과 역할에 대한 정보는 제공된 텍스트에서 직접적으로 명시되어 있지 않습니다. 텍스트는 실크 고양이 소년(Toby, Samuel)과 실크 고양이 소녀(Tiffany, Susie)에 대해 설명하고 있습니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_e3812ae37373195b931ad97018d62717"], "live_llm_retrieval_topk": ["su_e3812ae37373195b931ad97018d62717"], "v3_primary_replay": ["su_e3812ae37373195b931ad97018d62717"]}`
- Locator fields: `{"document_id": "73557605809705ab", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_e3812ae37373195b931ad97018d62717", "text_locator": {"chunk_id": "c154cb887de9efe4", "line_number": 112697, "section_id": "6d9b43f23617a1c0", "section_path": ["등장 가족", "실크 고양이 가족"], "section_type": "setting", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "세계관"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_e3812ae37373195b931ad97018d62717"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_e3812ae37373195b931ad97018d62717"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_e3812ae37373195b931ad97018d62717"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: failing lanes require row-level triage: v3_primary_replay:LLM_TRUE_PARTIAL_SYNTHESIS, live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `prompt_answer_renderer_triage`

## text_namu_v2_0077 (TEXT)

- Query: 미츠하는 타키를 만나려고 어디로 향했어
- Lane A answer: 미츠하는 타키를 만나기 위해 도쿄로 향했다.
- Lane B answer: 미츠하는 자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 도쿄로 향했다.
- Lane C answer: 미츠하는 자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 도쿄로 향했습니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"], "live_llm_retrieval_topk": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"], "v3_primary_replay": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"]}`
- Locator fields: `{"document_id": "4035db0b8289111a", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce", "text_locator": {"chunk_id": "b6212abe489bd65a", "line_number": 96481, "section_id": "d462e796db6f63c2", "section_path": ["스토리", "과거로 돌아간 후"], "section_type": "synopsis", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "줄거리"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_6d48d1ba9fa1ad85f5a5e84f2b77d0ce"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: failing lanes require row-level triage: v3_primary_replay:LLM_TRUE_PARTIAL_SYNTHESIS, live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `prompt_answer_renderer_triage`

## text_namu_v2_0084 (TEXT)

- Query: 소드아트 오디널 스케일은 어떤 극장판을 가리켜
- Lane A answer: 소드 아트 온라인은 일본에서 개봉한 극장판 애니메이션을 가리킵니다.
- Lane B answer: 소드 아트 온라인의 극장판 애니메이션이다.
- Lane C answer: 소드 아트 온라인 -오디널 스케일은 2017년 2월 18일에 일본에서 개봉한 소드 아트 온라인의 극장판 애니메이션이다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_4fe260722d1f2e526ccd32a465f737bb"], "live_llm_retrieval_topk": ["su_4fe260722d1f2e526ccd32a465f737bb"], "v3_primary_replay": ["su_4fe260722d1f2e526ccd32a465f737bb"]}`
- Locator fields: `{"document_id": "214902951f6edb9e", "document_version_id": "docv_sha256_c9c18da61956de64", "search_unit_id": "su_4fe260722d1f2e526ccd32a465f737bb", "text_locator": {"chunk_id": "46f4df85eb6afb34", "line_number": 41013, "section_id": "9aeb31447d88d471", "section_path": ["개요"], "section_type": "summary", "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl", "title": "소드 아트 온라인 -오디널 스케일-"}}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_4fe260722d1f2e526ccd32a465f737bb"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_4fe260722d1f2e526ccd32a465f737bb"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_4fe260722d1f2e526ccd32a465f737bb"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["document_id", "document_version_id", "search_unit_id", "text_locator"], "source_family": "TEXT"}}`
- Diagnosis: failing lanes require row-level triage: v3_primary_replay:LLM_TRUE_PARTIAL_SYNTHESIS, live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `prompt_answer_renderer_triage`

## gq_auto_012 (XLSX)

- Query: 2019년 2월 5호선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2019년 2월 5호선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.599) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D352: 대중교통구분=지하철 | 노선명=5호선 | 년월=201902 | 승차총승객수=15446522
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.532) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D602: 대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905 | 승차총승객수=1469681
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.525) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.522) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.518) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다.
- Lane C answer: 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_67883de1b446689033ed546cbd34ccd7"], "live_llm_retrieval_topk": ["su_67883de1b446689033ed546cbd34ccd7"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_614d184a7cf2fd15060607a7a98b62e6", "su_67883de1b446689033ed546cbd34ccd7", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"]}`
- Locator fields: `{"cell": "D352", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "15446522", "number_format": null, "range": "A352:D401", "row_label": "대중교통구분=지하철 | 노선명=5호선 | 년월=201902", "search_unit_id": "su_67883de1b446689033ed546cbd34ccd7", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_67883de1b446689033ed546cbd34ccd7"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_67883de1b446689033ed546cbd34ccd7"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_614d184a7cf2fd15060607a7a98b62e6", "su_67883de1b446689033ed546cbd34ccd7", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_018 (XLSX)

- Query: 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?
- Lane A answer: **Query:** 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?

**Short answer:** 국민건강보험공단_장기요양기관 시설별 현황_20240716.

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.636) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 C702: 장기요양기관코드=12717000382 | 장기요양기관이름=하얀민들레노인요양원 | 시도코드=27 | 우편번호=41786
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.537) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.536) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 I1052: 장기요양기관코드=12820000600 | 장기요양기관이름=신논현요양원 | 우편번호=21666 | 설치신고일자=2019-03-15
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.530) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.521) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 하얀민들레노인요양원의 우편번호는 41786입니다.
- Lane C answer: 41786
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_e0bb86f616fa782e5124c5421ea18109"], "live_llm_retrieval_topk": ["su_e0bb86f616fa782e5124c5421ea18109"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_b3d516e111b0a48402568d5e190780a9", "su_e0bb86f616fa782e5124c5421ea18109", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "C702", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "41786", "number_format": null, "range": "A702:J751", "row_label": "장기요양기관코드=12717000382 | 장기요양기관이름=하얀민들레노인요양원 | 시도코드=27", "search_unit_id": "su_e0bb86f616fa782e5124c5421ea18109", "sheet": "일반현황", "target_column": "우편번호", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_e0bb86f616fa782e5124c5421ea18109"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_e0bb86f616fa782e5124c5421ea18109"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_b3d516e111b0a48402568d5e190780a9", "su_e0bb86f616fa782e5124c5421ea18109", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_022 (XLSX)

- Query: 2017년 12월 9호선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2017년 12월 9호선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.627) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D452: 대중교통구분=지하철 | 노선명=9호선 | 년월=201712 | 승차총승객수=8048476
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.517) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.517) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.509) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.508) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2017년 12월 9호선의 승차총승객수는 8,048,476명입니다.
- Lane C answer: 8,048,476명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_708ed237c47efdd544422c45b6689a6e"], "live_llm_retrieval_topk": ["su_708ed237c47efdd544422c45b6689a6e"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_708ed237c47efdd544422c45b6689a6e", "su_b730bbddf0a9da442da84f360a2018e3"]}`
- Locator fields: `{"cell": "D452", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "8048476", "number_format": null, "range": "A452:D501", "row_label": "대중교통구분=지하철 | 노선명=9호선 | 년월=201712", "search_unit_id": "su_708ed237c47efdd544422c45b6689a6e", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_708ed237c47efdd544422c45b6689a6e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_708ed237c47efdd544422c45b6689a6e"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_708ed237c47efdd544422c45b6689a6e", "su_b730bbddf0a9da442da84f360a2018e3"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_023 (XLSX)

- Query: 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?
- Lane A answer: **Query:** 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?

**Short answer:** xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동.

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.586) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.454) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.440) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 C702: 장기요양기관코드=12717000382 | 장기요양기관이름=하얀민들레노인요양원 | 시도코드=27 | 우편번호=41786
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.405) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.403) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 대구광역시 북구 복현동입니다.
- Lane C answer: 대구광역시 북구 복현동
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "XLSX_CELL_LOCATOR_LOSS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_ae7e8fe6589ece39207854da3f983dd8"], "live_llm_retrieval_topk": ["su_ae7e8fe6589ece39207854da3f983dd8"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae7e8fe6589ece39207854da3f983dd8", "su_e0bb86f616fa782e5124c5421ea18109", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "G752", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "대구광역시 북구 복현동", "number_format": null, "range": "A752:J801", "row_label": "장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526", "search_unit_id": "su_ae7e8fe6589ece39207854da3f983dd8", "sheet": "일반현황", "target_column": "시도 시군구 법정동명", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_ae7e8fe6589ece39207854da3f983dd8"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": "XLSX_CELL_LOCATOR_LOSS", "cited_search_unit_ids": ["su_ae7e8fe6589ece39207854da3f983dd8"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {"su_ae7e8fe6589ece39207854da3f983dd8": ["row_label"]}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": false, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae7e8fe6589ece39207854da3f983dd8", "su_e0bb86f616fa782e5124c5421ea18109", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:XLSX_CELL_LOCATOR_LOSS
- Recommended next action: `repair_xlsx_locator_preservation`

## gq_auto_028 (XLSX)

- Query: 2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?
- Lane A answer: **Query:** 2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?

**Short answer:** xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동).

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.678) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.575) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.550) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.544) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.535) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 대구광역시 수성구 파동로51길 96 (파동)입니다.
- Lane C answer: 해오름요양원의 기관별 상세주소는 대구광역시 수성구 파동로51길 96 (파동)입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "live_llm_retrieval_topk": ["su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "J802", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "대구광역시 수성구 파동로51길 96 (파동)", "number_format": null, "range": "A802:J851", "row_label": "장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222", "search_unit_id": "su_e6286c1f20fc6b53d4fad7b1f9bd49b4", "sheet": "일반현황", "target_column": "기관별 상세주소", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_031 (XLSX)

- Query: 2018년 7월 8호선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2018년 7월 8호선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.622) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.506) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D452: 대중교통구분=지하철 | 노선명=9호선 | 년월=201712 | 승차총승객수=8048476
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.500) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D202: 대중교통구분=지하철 | 노선명=일산선 | 년월=201809 | 승차총승객수=3258215
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.498) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.497) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2018년 7월 8호선의 승차총승객수는 5,630,084명입니다.
- Lane C answer: 2018년 7월 8호선의 승차총승객수는 5,630,084명입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_4c006bc96bb885de02f797b6161af1e3"], "live_llm_retrieval_topk": ["su_4c006bc96bb885de02f797b6161af1e3"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_708ed237c47efdd544422c45b6689a6e", "su_f8375698d57fe2cd6c31aef605b22347"]}`
- Locator fields: `{"cell": "D402", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "5630084", "number_format": null, "range": "A402:D451", "row_label": "대중교통구분=지하철 | 노선명=8호선 | 년월=201807", "search_unit_id": "su_4c006bc96bb885de02f797b6161af1e3", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_4c006bc96bb885de02f797b6161af1e3"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_4c006bc96bb885de02f797b6161af1e3"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_708ed237c47efdd544422c45b6689a6e", "su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_034 (XLSX)

- Query: 2018년 5월 의정부경전철의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2018년 5월 의정부경전철의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.638) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.516) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.514) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D602: 대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905 | 승차총승객수=1469681
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.511) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D352: 대중교통구분=지하철 | 노선명=5호선 | 년월=201902 | 승차총승객수=15446522
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.505) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2018년 5월 의정부경전철의 승차총승객수는 1,095,397명입니다.
- Lane C answer: 1,095,397명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_b730bbddf0a9da442da84f360a2018e3"], "live_llm_retrieval_topk": ["su_b730bbddf0a9da442da84f360a2018e3"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_611a25006642d14eadbf630b401ce758", "su_67883de1b446689033ed546cbd34ccd7", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"]}`
- Locator fields: `{"cell": "D552", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "1095397", "number_format": null, "range": "A552:D601", "row_label": "대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805", "search_unit_id": "su_b730bbddf0a9da442da84f360a2018e3", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_b730bbddf0a9da442da84f360a2018e3"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_b730bbddf0a9da442da84f360a2018e3"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_611a25006642d14eadbf630b401ce758", "su_67883de1b446689033ed546cbd34ccd7", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_035 (XLSX)

- Query: 2018년 11월 3호선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2018년 11월 3호선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.631) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.535) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.528) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.527) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D2: 대중교통구분=지하철 | 노선명=1호선 | 년월=201711 | 승차총승객수=8633618
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.525) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2018년 11월 3호선의 승차총승객수는 17,956,555명입니다.
- Lane C answer: 17,956,555명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_17998243c64babb947113d3f2beaf68b"], "live_llm_retrieval_topk": ["su_17998243c64babb947113d3f2beaf68b"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_767da3be1a17459b77e09f3d4b7279b5", "su_b730bbddf0a9da442da84f360a2018e3"]}`
- Locator fields: `{"cell": "D52", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "17956555", "number_format": null, "range": "A52:D101", "row_label": "대중교통구분=지하철 | 노선명=3호선 | 년월=201811", "search_unit_id": "su_17998243c64babb947113d3f2beaf68b", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_767da3be1a17459b77e09f3d4b7279b5", "su_b730bbddf0a9da442da84f360a2018e3"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_037 (XLSX)

- Query: 2019년 4월 안산선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2019년 4월 안산선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.597) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.521) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D202: 대중교통구분=지하철 | 노선명=일산선 | 년월=201809 | 승차총승객수=3258215
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.512) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D302: 대중교통구분=지하철 | 노선명=수인선 | 년월=201902 | 승차총승객수=1124736
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.512) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.503) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D602: 대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905 | 승차총승객수=1469681

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2019년 4월 안산선의 승차총승객수는 4,230,809명입니다.
- Lane C answer: 2,308,090명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_614d184a7cf2fd15060607a7a98b62e6"], "live_llm_retrieval_topk": ["su_614d184a7cf2fd15060607a7a98b62e6"], "v3_primary_replay": ["su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_eb03e5cc1216f7e6c628133dc7d57e53", "su_f8375698d57fe2cd6c31aef605b22347"]}`
- Locator fields: `{"cell": "D152", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "4230809", "number_format": null, "range": "A152:D201", "row_label": "대중교통구분=지하철 | 노선명=안산선 | 년월=201904", "search_unit_id": "su_614d184a7cf2fd15060607a7a98b62e6", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_614d184a7cf2fd15060607a7a98b62e6"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_614d184a7cf2fd15060607a7a98b62e6"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_eb03e5cc1216f7e6c628133dc7d57e53", "su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `row_level_answer_span_triage`

## gq_auto_038 (XLSX)

- Query: 2018년 9월 일산선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2018년 9월 일산선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.610) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D202: 대중교통구분=지하철 | 노선명=일산선 | 년월=201809 | 승차총승객수=3258215
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.542) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.536) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.532) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.530) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D452: 대중교통구분=지하철 | 노선명=9호선 | 년월=201712 | 승차총승객수=8048476

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2018년 9월 일산선의 승차총승객수는 3,258,215명입니다.
- Lane C answer: 3,258,215명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_f8375698d57fe2cd6c31aef605b22347"], "live_llm_retrieval_topk": ["su_f8375698d57fe2cd6c31aef605b22347"], "v3_primary_replay": ["su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_708ed237c47efdd544422c45b6689a6e", "su_f8375698d57fe2cd6c31aef605b22347"]}`
- Locator fields: `{"cell": "D202", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "3258215", "number_format": null, "range": "A202:D251", "row_label": "대중교통구분=지하철 | 노선명=일산선 | 년월=201809", "search_unit_id": "su_f8375698d57fe2cd6c31aef605b22347", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_708ed237c47efdd544422c45b6689a6e", "su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_auto_043 (XLSX)

- Query: 2019년 3월에 지정된 신논현요양원의 설치신고일자는 언제입니까?
- Lane A answer: **Query:** 2019년 3월에 지정된 신논현요양원의 설치신고일자는 언제입니까?

**Short answer:** 국민건강보험공단_장기요양기관 시설별 현황_20240716.

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.638) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 I1052: 장기요양기관코드=12820000600 | 장기요양기관이름=신논현요양원 | 우편번호=21666 | 설치신고일자=2019-03-15
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.451) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.435) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.426) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.419) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 C702: 장기요양기관코드=12717000382 | 장기요양기관이름=하얀민들레노인요양원 | 시도코드=27 | 우편번호=41786

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2019년 3월 15일입니다.
- Lane C answer: 2019년 3월 15일입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_4e2cedbb7866f2c7e2191766e2a5c3e8"], "live_llm_retrieval_topk": ["su_4e2cedbb7866f2c7e2191766e2a5c3e8"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e0bb86f616fa782e5124c5421ea18109"]}`
- Locator fields: `{"cell": "I1052", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "2019-03-15", "number_format": null, "range": "A1052:J1101", "row_label": "장기요양기관코드=12820000600 | 장기요양기관이름=신논현요양원 | 우편번호=21666", "search_unit_id": "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "sheet": "일반현황", "target_column": "설치신고일자", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_4e2cedbb7866f2c7e2191766e2a5c3e8"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_4e2cedbb7866f2c7e2191766e2a5c3e8"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e0bb86f616fa782e5124c5421ea18109"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `row_level_answer_span_triage`

## gq_auto_044 (XLSX)

- Query: 2022년 5월에 지정된 인천은빛요양원의 기관별 상세주소는 무엇입니까?
- Lane A answer: **Query:** 2022년 5월에 지정된 인천은빛요양원의 기관별 상세주소는 무엇입니까?

**Short answer:** xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩).

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.709) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.556) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.542) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.531) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J5002: 장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773 (석성면)
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.529) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2022년 5월에 지정된 인천은빛요양원의 기관별 상세 주소는 인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)입니다.
- Lane C answer: 인천은빛요양원의 기관별 상세 주소는 인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a"], "live_llm_retrieval_topk": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a"], "v3_primary_replay": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae23062eacdc13d9e77a0cef5b049525", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "J1102", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)", "number_format": null, "range": "A1102:J1151", "row_label": "장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540", "search_unit_id": "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "sheet": "일반현황", "target_column": "기관별 상세주소", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae23062eacdc13d9e77a0cef5b049525", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_date_number_format_001 (XLSX)

- Query: 2008년 6월에 지정된 청운노인요양원의 지정일자는 정확히 언제입니까?
- Lane A answer: **Query:** 2008년 6월에 지정된 청운노인요양원의 지정일자는 정확히 언제입니까?

**Short answer:** 국민건강보험공단_장기요양기관 시설별 현황_20240716.

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.613) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.560) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.460) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.458) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 I1052: 장기요양기관코드=12820000600 | 장기요양기관이름=신논현요양원 | 우편번호=21666 | 설치신고일자=2019-03-15
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.437) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2008년 6월 25일입니다.
- Lane C answer: 2008년 6월 25일입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "live_llm_retrieval_topk": {"answer_score": 0.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH", "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "live_llm_retrieval_topk": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "H2", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "2008-06-25", "number_format": null, "range": "A2:J51", "row_label": "장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001", "search_unit_id": "su_0c48e5c6be0a69c80d5e2a7294279b08", "sheet": "일반현황", "target_column": "지정일자", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_4e2cedbb7866f2c7e2191766e2a5c3e8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:LLM_EXPECTED_SPAN_MISMATCH, live_llm_query_bound_oracle:LLM_EXPECTED_SPAN_MISMATCH
- Recommended next action: `row_level_answer_span_triage`

## gq_xlsx_lookup_001 (XLSX)

- Query: 2017년 11월 1호선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2017년 11월 1호선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.611) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D2: 대중교통구분=지하철 | 노선명=1호선 | 년월=201711 | 승차총승객수=8633618
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.575) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D52: 대중교통구분=지하철 | 노선명=3호선 | 년월=201811 | 승차총승객수=17956555
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.567) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D202: 대중교통구분=지하철 | 노선명=일산선 | 년월=201809 | 승차총승객수=3258215
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.564) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D452: 대중교통구분=지하철 | 노선명=9호선 | 년월=201712 | 승차총승객수=8048476
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.563) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2017년 11월 1호선의 승차총승객수는 8,633,618명입니다.
- Lane C answer: 8,633,618명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_767da3be1a17459b77e09f3d4b7279b5"], "live_llm_retrieval_topk": ["su_767da3be1a17459b77e09f3d4b7279b5"], "v3_primary_replay": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_708ed237c47efdd544422c45b6689a6e", "su_767da3be1a17459b77e09f3d4b7279b5", "su_f8375698d57fe2cd6c31aef605b22347"]}`
- Locator fields: `{"cell": "D2", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "8633618", "number_format": null, "range": "A2:D51", "row_label": "대중교통구분=지하철 | 노선명=1호선 | 년월=201711", "search_unit_id": "su_767da3be1a17459b77e09f3d4b7279b5", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_767da3be1a17459b77e09f3d4b7279b5"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_767da3be1a17459b77e09f3d4b7279b5"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_17998243c64babb947113d3f2beaf68b", "su_4c006bc96bb885de02f797b6161af1e3", "su_708ed237c47efdd544422c45b6689a6e", "su_767da3be1a17459b77e09f3d4b7279b5", "su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_lookup_004 (XLSX)

- Query: 2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.595) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D602: 대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905 | 승차총승객수=1469681
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.477) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D302: 대중교통구분=지하철 | 노선명=수인선 | 년월=201902 | 승차총승객수=1124736
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.471) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D352: 대중교통구분=지하철 | 노선명=5호선 | 년월=201902 | 승차총승객수=15446522
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.465) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.452) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2019년 5월 우이신설선의 승차총승객수는 1,469,681명입니다.
- Lane C answer: 1,469,681명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_eb03e5cc1216f7e6c628133dc7d57e53"], "live_llm_retrieval_topk": ["su_eb03e5cc1216f7e6c628133dc7d57e53"], "v3_primary_replay": ["su_614d184a7cf2fd15060607a7a98b62e6", "su_67883de1b446689033ed546cbd34ccd7", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"]}`
- Locator fields: `{"cell": "D602", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "1469681", "number_format": null, "range": "A602:D602", "row_label": "대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905", "search_unit_id": "su_eb03e5cc1216f7e6c628133dc7d57e53", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_eb03e5cc1216f7e6c628133dc7d57e53"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_eb03e5cc1216f7e6c628133dc7d57e53"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_614d184a7cf2fd15060607a7a98b62e6", "su_67883de1b446689033ed546cbd34ccd7", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_b730bbddf0a9da442da84f360a2018e3", "su_eb03e5cc1216f7e6c628133dc7d57e53"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_lookup_005 (XLSX)

- Query: 2018년 4월 경인선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2018년 4월 경인선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.609) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.535) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D552: 대중교통구분=지하철 | 노선명=의정부경전철 | 년월=201805 | 승차총승객수=1095397
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.525) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D302: 대중교통구분=지하철 | 노선명=수인선 | 년월=201902 | 승차총승객수=1124736
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.505) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D402: 대중교통구분=지하철 | 노선명=8호선 | 년월=201807 | 승차총승객수=5630084
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.501) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2018년 4월 경인선의 승차총승객수는 10,356,250명입니다.
- Lane C answer: 10,356,250명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_611a25006642d14eadbf630b401ce758"], "live_llm_retrieval_topk": ["su_611a25006642d14eadbf630b401ce758"], "v3_primary_replay": ["su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_b730bbddf0a9da442da84f360a2018e3"]}`
- Locator fields: `{"cell": "D102", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "10356250", "number_format": null, "range": "A102:D151", "row_label": "대중교통구분=지하철 | 노선명=경인선 | 년월=201804", "search_unit_id": "su_611a25006642d14eadbf630b401ce758", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_611a25006642d14eadbf630b401ce758"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_611a25006642d14eadbf630b401ce758"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_4c006bc96bb885de02f797b6161af1e3", "su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_b730bbddf0a9da442da84f360a2018e3"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_lookup_006 (XLSX)

- Query: 2019년 2월 수인선의 승차총승객수는 몇 명입니까?
- Lane A answer: **Query:** 2019년 2월 수인선의 승차총승객수는 몇 명입니까?

**Short answer:** 서울시 대중교통 수단별 이용 현황(2017.

**Supporting passages:**
1. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.570) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D302: 대중교통구분=지하철 | 노선명=수인선 | 년월=201902 | 승차총승객수=1124736
2. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.511) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D102: 대중교통구분=지하철 | 노선명=경인선 | 년월=201804 | 승차총승객수=10356250
3. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.501) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D152: 대중교통구분=지하철 | 노선명=안산선 | 년월=201904 | 승차총승객수=4230809
4. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.501) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D602: 대중교통구분=지하철 | 노선명=우이신설선 | 년월=201905 | 승차총승객수=1469681
5. [docv_sha256_bd2ccf8a5814cef5#xlsx_business_structured] (score=0.486) 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 D202: 대중교통구분=지하철 | 노선명=일산선 | 년월=201809 | 승차총승객수=3258215

**Sources:** docv_sha256_bd2ccf8a5814cef5
- Lane B answer: 2019년 2월 수인선의 승차총승객수는 1,124,736명입니다.
- Lane C answer: 1,124,736명
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_abf379a0b7fef4ee99b6c2141d94cdd2"], "live_llm_retrieval_topk": ["su_abf379a0b7fef4ee99b6c2141d94cdd2"], "v3_primary_replay": ["su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_eb03e5cc1216f7e6c628133dc7d57e53", "su_f8375698d57fe2cd6c31aef605b22347"]}`
- Locator fields: `{"cell": "D302", "displayed_value": null, "document_version_id": "docv_sha256_bd2ccf8a5814cef5", "normalized_value": "1124736", "number_format": null, "range": "A302:D351", "row_label": "대중교통구분=지하철 | 노선명=수인선 | 년월=201902", "search_unit_id": "su_abf379a0b7fef4ee99b6c2141d94cdd2", "sheet": "철도", "target_column": "승차총승객수", "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_abf379a0b7fef4ee99b6c2141d94cdd2"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_abf379a0b7fef4ee99b6c2141d94cdd2"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_611a25006642d14eadbf630b401ce758", "su_614d184a7cf2fd15060607a7a98b62e6", "su_abf379a0b7fef4ee99b6c2141d94cdd2", "su_eb03e5cc1216f7e6c628133dc7d57e53", "su_f8375698d57fe2cd6c31aef605b22347"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_lookup_007 (XLSX)

- Query: 2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?
- Lane A answer: **Query:** 2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?

**Short answer:** 국민건강보험공단_장기요양기관 시설별 현황_20240716.

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.674) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.669) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.567) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.536) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J1102: 장기요양기관코드=12820000827 | 장기요양기관이름=인천은빛요양원 | 우편번호=21540 | 기관별 상세주소=인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.535) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J5002: 장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773 (석성면)

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2008년 6월에 지정된 청운노인요양원의 기관별 상세 주소는 서울특별시 종로구 비봉길 76 (구기동)입니다.
- Lane C answer: 청운노인요양원의 기관별 상세주소는 서울특별시 종로구 비봉길 76 (구기동)입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "PASS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_b3d516e111b0a48402568d5e190780a9"], "live_llm_retrieval_topk": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae23062eacdc13d9e77a0cef5b049525", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "J2", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "서울특별시 종로구 비봉길 76 (구기동)", "number_format": null, "range": "A2:J51", "row_label": "장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001", "search_unit_id": "su_b3d516e111b0a48402568d5e190780a9", "sheet": "일반현황", "target_column": "기관별 상세주소", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_b3d516e111b0a48402568d5e190780a9"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_2c9d9ffc8ee90e1b59cbd599e15de21a", "su_ae23062eacdc13d9e77a0cef5b049525", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: all lanes passed under diagnostic scoring
- Recommended next action: `no_action`

## gq_xlsx_lookup_008 (XLSX)

- Query: 2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?
- Lane A answer: **Query:** 2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?

**Short answer:** xlsx / 일반현황 J5002: 장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773 (석성면).

**Supporting passages:**
1. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.695) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J5002: 장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176 | 기관별 상세주소=충청남도 부여군 석성면 왕릉로 773 (석성면)
2. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.592) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J802: 장기요양기관코드=12726000180 | 장기요양기관이름=해오름요양원 | 우편번호=42222 | 기관별 상세주소=대구광역시 수성구 파동로51길 96 (파동)
3. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.584) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 J2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 기관별 상세주소=서울특별시 종로구 비봉길 76 (구기동)
4. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.570) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 H2: 장기요양기관코드=11111000006 | 장기요양기관이름=청운노인요양원 | 우편번호=03001 | 지정일자=2008-06-25
5. [docv_sha256_905af8cbadec7244#xlsx_business_structured] (score=0.561) 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 G752: 장기요양기관코드=12723000318 | 장기요양기관이름=해뜨는요양원2 | 우편번호=41526 | 시도 시군구 법정동명=대구광역시 북구 복현동

**Sources:** docv_sha256_905af8cbadec7244
- Lane B answer: 2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 충청남도 부여군 석성면 왕릉로 773 (석성면)입니다.
- Lane C answer: 부여효요양원의 기관별 상세 주소는 충청남도 부여군 석성면 왕릉로 773 (석성면)입니다.
- Scores: `{"live_llm_query_bound_oracle": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}, "live_llm_retrieval_topk": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "FAIL_CLOSED"}, "v3_primary_replay": {"answer_score": 1.0, "citation_support_score": 1.0, "score_status": "PASS"}}`
- Failure category: `{"live_llm_query_bound_oracle": "PASS", "live_llm_retrieval_topk": "XLSX_CELL_LOCATOR_LOSS", "v3_primary_replay": "PASS"}`
- Cited SearchUnit IDs: `{"live_llm_query_bound_oracle": ["su_ae23062eacdc13d9e77a0cef5b049525"], "live_llm_retrieval_topk": ["su_ae23062eacdc13d9e77a0cef5b049525"], "v3_primary_replay": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_ae23062eacdc13d9e77a0cef5b049525", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"]}`
- Locator fields: `{"cell": "J5002", "displayed_value": null, "document_version_id": "docv_sha256_905af8cbadec7244", "normalized_value": "충청남도 부여군 석성면 왕릉로 773 (석성면)", "number_format": null, "range": "A5002:J5051", "row_label": "장기요양기관코드=14476000092 | 장기요양기관이름=부여효요양원 | 우편번호=33176", "search_unit_id": "su_ae23062eacdc13d9e77a0cef5b049525", "sheet": "일반현황", "target_column": "기관별 상세주소", "workbook": "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"}`
- LLM-generated locator validation: `{"live_llm_query_bound_oracle": {"category": null, "cited_search_unit_ids": ["su_ae23062eacdc13d9e77a0cef5b049525"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": true, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "live_llm_retrieval_topk": {"category": "XLSX_CELL_LOCATOR_LOSS", "cited_search_unit_ids": ["su_ae23062eacdc13d9e77a0cef5b049525"], "generated_by_llm": true, "generated_locator_count": 1, "mismatched_fields_by_search_unit_id": {"su_ae23062eacdc13d9e77a0cef5b049525": ["row_label"]}, "missing_fields_by_search_unit_id": {}, "missing_locator_for_search_unit_ids": [], "ok": false, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}, "v3_primary_replay": {"category": null, "cited_search_unit_ids": ["su_0c48e5c6be0a69c80d5e2a7294279b08", "su_ae23062eacdc13d9e77a0cef5b049525", "su_ae7e8fe6589ece39207854da3f983dd8", "su_b3d516e111b0a48402568d5e190780a9", "su_e6286c1f20fc6b53d4fad7b1f9bd49b4"], "generated_by_llm": false, "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.", "ok": null, "required_fields": ["workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id"], "source_family": "XLSX"}}`
- Diagnosis: failing lanes require row-level triage: live_llm_retrieval_topk:XLSX_CELL_LOCATOR_LOSS
- Recommended next action: `repair_xlsx_locator_preservation`
