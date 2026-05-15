from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"


def test_progress_doc_current_board_uses_latest_blockers_not_historical_xlsx_pass():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_board = text.split("## Track Board", 1)[1].split("## 2026-05-14", 1)[0]
    current_update = text.split("## 2026-05-14", 1)[1].split("## 2026-05-13", 1)[0]

    assert "DIAGNOSTIC_POLICY_PACKET_READY" in current_board
    assert "raw answer/citation leakage reprobe `PASS`" in current_board
    assert "Old raw hidden/excluded answer/citation leakage blocker is resolved" in current_board
    assert "Evidence readiness `7/7`" in current_board
    assert "clean pass `7`" in current_board
    assert "REPORT_ONLY_READY" in current_update
    assert "DIAGNOSTIC_PREFLIGHT_READY" in current_update
    assert "XLSX blocker `false`, PDF blocker `false`" in current_update
    assert "PDF answer/citation packet: `DIAGNOSTIC_POLICY_PACKET_READY`" in current_update
    assert "Tuning run started: `false`" in current_update
    assert "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LEAKAGE" not in current_board
    assert "PDF blocker `true`" not in current_update
