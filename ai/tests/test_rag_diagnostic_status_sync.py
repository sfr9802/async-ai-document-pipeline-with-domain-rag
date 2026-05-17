from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"


def test_progress_doc_current_board_uses_latest_scored_baseline_not_backend_unavailable():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "official_answer_citation_agentic_loop_measurement_partial_gpu_index_live_generation" in current_text
    assert "official_metric_execution_started=true" in current_text
    assert "official_scoring_attempt_count=29" in current_text
    assert "PASS=8" in current_text
    assert "CITATION_UNSUPPORTED=11" in current_text
    assert "PARTIAL_OR_UNSUPPORTED=10" in current_text
    assert "XLSX runtime candidate" in current_text
    assert "XLSX=19/19" in current_text
    assert "PDF table/value candidate" in current_text
    assert "PASS=29/29" in current_text
    assert "official_answer_citation_agentic_loop_run_v1" in current_text
    assert "scored_count=29" in current_text
    assert "PASS=1" in current_text
    assert "faiss_gpu_used=true" in current_text
    assert "eval/indexes/rag-data" in current_text
    assert "report-only" in current_text
    assert "pytest ai/tests --rag-current -q" in current_text
    assert "full ai/tests is broad/nightly diagnostic only" in current_text
    assert "rag_current_eval_status.jsonl" in current_text

    assert "SCORER_BACKEND_UNAVAILABLE" not in current_text
    assert "scorer/backend is unavailable" not in current_text
    assert "wire or start the official answer/citation scorer/backend" not in current_text
    assert "Wire or start the official answer/citation scorer/backend" not in current_text


def test_progress_doc_does_not_keep_stale_current_profile_test_count():
    text = PROGRESS_DOC.read_text(encoding="utf-8")

    assert "Current verification:" in text
    assert "0 skipped" in text
    assert "0 failed" in text
    assert "current focused profile is 61 tests" not in text


def test_progress_doc_explains_pre_execution_smoke_is_not_latest_metric_status():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "pre-execution artifact" in current_text
    assert "official_metric_execution_started=false" in current_text
    assert "must not be read\nas the latest metric execution status" in current_text


def test_progress_doc_scorer_backend_unavailable_only_in_short_history():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    headings_with_unavailable = []
    current_heading = ""
    current_body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if "SCORER_BACKEND_UNAVAILABLE" in "\n".join(current_body):
                headings_with_unavailable.append(current_heading)
            current_heading = line.removeprefix("## ").strip()
            current_body = []
        else:
            current_body.append(line)
    if "SCORER_BACKEND_UNAVAILABLE" in "\n".join(current_body):
        headings_with_unavailable.append(current_heading)

    assert headings_with_unavailable == ["Short History"]
