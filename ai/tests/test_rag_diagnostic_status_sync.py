from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"


def test_progress_doc_current_board_uses_latest_scored_baseline_not_backend_unavailable():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_board = text.split("## Track Board", 1)[1].split("## 2026-05-14", 1)[0]
    current_status = text.split("## Current Status", 1)[1].split("## Track Board", 1)[0]
    next_steps = text.split("## Next Recommended Steps", 1)[1].split("## Update Policy", 1)[0]

    assert "official_answer_citation_metric_first_run_scored_baseline_partial" in current_status
    assert "official_metric_execution_started=true" in current_status
    assert "official_scoring_attempt_count=29" in current_status
    assert "PASS=8" in current_status
    assert "CITATION_UNSUPPORTED=11" in current_status
    assert "PARTIAL_OR_UNSUPPORTED=10" in current_status
    assert "DIAGNOSTIC_POLICY_PACKET_READY" in current_board
    assert "row/cell citation precision + target-column answer extraction candidate repair" in current_board
    assert "preserve `text_namu_v2_0017` diagnostic warning" in current_board
    assert "inspect table/row value answer generation failures" in current_board
    assert "XLSX candidate repair, report-only" in next_steps

    for section in (current_status, current_board, next_steps):
        assert "SCORER_BACKEND_UNAVAILABLE" not in section
        assert "scorer/backend is unavailable" not in section
        assert "wire or start the official answer/citation scorer/backend" not in section
        assert "Wire or start the official answer/citation scorer/backend" not in section


def test_progress_doc_scorer_backend_unavailable_only_in_superseded_history():
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

    assert headings_with_unavailable == ["2026-05-16 Official Answer/Citation Metric First Run (superseded)"]
