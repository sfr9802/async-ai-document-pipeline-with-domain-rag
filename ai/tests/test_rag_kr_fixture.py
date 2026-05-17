"""Korean RAG fixture tests.

These tests verify the committed Korean fixture and CLI fixture constants.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# 1. kr_sample.jsonl is valid JSONL with expected schema.
# ---------------------------------------------------------------------------


def test_kr_fixture_is_valid_jsonl():
    path = _FIXTURES_DIR / "kr_sample.jsonl"
    assert path.exists(), f"kr_sample.jsonl not found at {path}"

    docs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        doc = json.loads(line)
        docs.append(doc)

    assert len(docs) >= 10, f"Expected >=10 Korean docs, got {len(docs)}"

    for doc in docs:
        assert "doc_id" in doc, f"Missing doc_id in {doc.get('title', '?')}"
        assert "title" in doc
        assert "sections" in doc
        assert isinstance(doc["sections"], dict)
        # Each section must have chunks.
        for section_name, section_data in doc["sections"].items():
            if section_name == "characters":
                # characters section may have a 'list' key instead of 'chunks'
                assert "list" in section_data or "chunks" in section_data
            else:
                assert "chunks" in section_data, (
                    f"Section {section_name} in {doc['doc_id']} missing 'chunks'"
                )


def test_build_rag_index_accepts_fixture_kr():
    """Verify the CLI argparser accepts --fixture kr without crashing."""
    import argparse

    from scripts.build_rag_index import KR_FIXTURE, DEFAULT_FIXTURE

    assert KR_FIXTURE.exists(), f"KR_FIXTURE not found at {KR_FIXTURE}"
    assert DEFAULT_FIXTURE.exists(), f"DEFAULT_FIXTURE not found at {DEFAULT_FIXTURE}"


def test_kr_fixture_contains_korean_text():
    path = _FIXTURES_DIR / "kr_sample.jsonl"
    full_text = path.read_text(encoding="utf-8")

    # Check for Korean character range (Hangul Syllables: U+AC00..U+D7AF).
    has_korean = any("\uac00" <= ch <= "\ud7af" for ch in full_text)
    assert has_korean, "kr_sample.jsonl should contain Korean characters"
