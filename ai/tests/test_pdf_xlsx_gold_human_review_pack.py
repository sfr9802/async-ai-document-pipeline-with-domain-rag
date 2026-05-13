from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_WORKER_ROOT = ROOT / "ai"
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


review_pack = load_module(
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_gold_human_review_pack.py",
    "rag_pdf_xlsx_gold_human_review_pack_for_tests",
)


def test_review_pack_keeps_gold_files_and_user_decisions_blank(tmp_path: Path):
    fixture = make_source_fixture(tmp_path)
    gold_before = fixture["gold_file"].read_text(encoding="utf-8")

    manifest = review_pack.run_pack(
        source_artifact_dir=fixture["source_artifact_dir"],
        output_root=tmp_path / "runs",
        run_id="20260506T000000Z",
        gold_files=[fixture["gold_file"]],
    )

    assert fixture["gold_file"].read_text(encoding="utf-8") == gold_before
    assert manifest["status"] == "PASS"
    assert manifest["gold_files_modified"] is False
    assert manifest["existing_gold_csv_overwritten"] is False
    assert manifest["review_pack_row_count"] == 2
    assert manifest["official_xlsx_answer_eval_denominator"] == 0
    assert manifest["promotion_evidence"] is False
    assert manifest["user_decision_columns_blank"] is True
    assert manifest["source_artifact_dir"].endswith("source_probe")

    rows = read_csv(Path(manifest["outputs"]["xlsx_gold_human_review_pack_csv"]["path"]))
    assert len(rows) == 2
    for row in rows:
        for column in review_pack.USER_DECISION_COLUMNS:
            assert column in row
            assert row[column] == ""

    first = rows[0]
    assert first["expected_answer_text_existing"] == "Station A"
    assert first["must_contain_terms_existing"] == '["GOLD_ONLY_TERM", "ridership"]'
    assert first["user_expected_answer_text"] == ""
    assert first["user_required_target_values"] == ""


def test_review_pack_keyword_triage_and_jsonl_are_diagnostic_only(tmp_path: Path):
    fixture = make_source_fixture(tmp_path)

    manifest = review_pack.run_pack(
        source_artifact_dir=fixture["source_artifact_dir"],
        output_root=tmp_path / "runs",
        run_id="20260506T000001Z",
        gold_files=[fixture["gold_file"]],
    )

    assert manifest["keyword_echo_triage_row_count"] == 1
    assert manifest["human_review_required_count"] == 1
    assert manifest["diagnostic_only"] is True
    assert manifest["diagnostic_llm_answers_are_gold"] is False
    assert manifest["gold_intent_suggestions_used_for_scoring"] is False
    assert manifest["expected_answer_text_promoted_to_scoring_target"] is False
    assert manifest["must_contain_terms_promoted_to_scoring_target"] is False

    triage_rows = read_jsonl(Path(manifest["outputs"]["xlsx_keyword_echo_triage_jsonl"]["path"]))
    assert len(triage_rows) == 1
    assert triage_rows[0]["diagnostic_only"] is True
    assert triage_rows[0]["promotion_evidence"] is False
    assert triage_rows[0]["triage_label_suggested"] in review_pack.TRIAGE_LABELS

    review_rows = read_jsonl(Path(manifest["outputs"]["xlsx_gold_human_review_pack_jsonl"]["path"]))
    assert len(review_rows) == 2
    assert all(row["official_xlsx_answer_eval_denominator"] == 0 for row in review_rows)
    assert all(row["promotion_evidence"] is False for row in review_rows)

    csv_rows = read_csv(Path(manifest["outputs"]["xlsx_keyword_echo_triage_csv"]["path"]))
    assert len(csv_rows) == 1
    assert csv_rows[0]["query_id"] == "q_keyword"


def make_source_fixture(tmp_path: Path) -> dict[str, Path]:
    source_artifact_dir = tmp_path / "source_probe"
    source_artifact_dir.mkdir()
    source_inputs_dir = tmp_path / "source_inputs"
    source_inputs_dir.mkdir()

    answer_generation_inputs = source_inputs_dir / "answer_generation_inputs.jsonl"
    evidence_objects = source_inputs_dir / "evidence_objects.jsonl"
    compiled_answers = source_inputs_dir / "compiled_answers.jsonl"

    source_rows = [
        {
            "query_id": "q_keyword",
            "track": "XLSX",
            "query": "station ridership",
            "expected_answer_shape": "TABLE_ROW_VALUE",
            "expected_answer_text": "Station A",
            "must_contain_terms": ["GOLD_ONLY_TERM", "ridership"],
        },
        {
            "query_id": "q_policy",
            "track": "XLSX",
            "query": "hidden row value",
            "expected_answer_shape": "TABLE_ROW_VALUE",
            "expected_answer_text": "review required",
            "must_contain_terms": ["hidden"],
        },
    ]
    evidence_rows = [
        {
            "query_id": "q_keyword",
            "selected_search_unit_id": "su-1",
            "content_source_fields": ["context.cell_values[0]"],
            "content_summary": "Row Station A / column ridership has value 100.",
            "evidence_object": {
                "sheet": "Sheet1",
                "range": "A1:B2",
                "content_summary": "Row Station A / column ridership has value 100.",
                "header_context": ["station", "ridership"],
                "row_values": [{"column_label": "ridership", "row_label": "Station A", "value": "100"}],
                "cell_values": [{"column_label": "ridership", "row_label": "Station A", "value": "100"}],
                "content_source_fields": ["context.cell_values[0]"],
                "citation_locator": {"sheet": "Sheet1", "range": "A1:B2", "search_unit_id": "su-1", "rank": 1},
            },
        },
        {
            "query_id": "q_policy",
            "selected_search_unit_id": "",
            "content_source_fields": [],
            "content_summary": "",
            "evidence_object": {},
        },
    ]
    compiled_rows = [
        {
            "query_id": "q_keyword",
            "compiler_status": "COMPILED",
            "compiled_answer": {"answer": "Station A ridership is 100.", "answer_shape": "TABLE_ROW_VALUE"},
        },
        {
            "query_id": "q_policy",
            "compiler_status": "ABSTAIN",
            "compiled_answer": {"answer": "", "answer_shape": "ABSTAIN"},
        },
    ]
    probe_inputs = [
        {
            "query_id": "q_keyword",
            "track": "XLSX",
            "query": "station ridership",
            "expected_answer_shape": "TABLE_ROW_VALUE",
            "answer_allowed": True,
            "fail_closed_reason": "",
            "answer_prompt_payload": {
                "citation_locator": {"sheet": "Sheet1", "range": "A1:B2", "search_unit_id": "su-1", "rank": 1},
                "compiled_deterministic_draft": {"answer": "Station A ridership is 100."},
                "evidence": {
                    "sheet": "Sheet1",
                    "range": "A1:B2",
                    "header_context": ["station", "ridership"],
                    "row_values": [{"column_label": "ridership", "row_label": "Station A", "value": "100"}],
                    "cell_values": [{"column_label": "ridership", "row_label": "Station A", "value": "100"}],
                },
            },
        },
        {
            "query_id": "q_policy",
            "track": "XLSX",
            "query": "hidden row value",
            "expected_answer_shape": "TABLE_ROW_VALUE",
            "answer_allowed": False,
            "fail_closed_reason": "POLICY_PENDING_HIDDEN_CONTENT",
            "answer_prompt_payload": {},
        },
    ]
    probe_outputs = [
        {
            "query_id": "q_keyword",
            "track": "XLSX",
            "answer_allowed": True,
            "answer": "Station A",
            "answer_type": "CELL_VALUE",
            "abstain_reason": "",
            "citations": [{"sheet": "Sheet1", "range": "A1:B2", "source": "selected_searchunit_payload"}],
            "unsupported_claims": [],
            "llm_keyword_echo_only": True,
            "llm_gold_leakage_suspected": False,
        },
        {
            "query_id": "q_policy",
            "track": "XLSX",
            "answer_allowed": False,
            "answer": "",
            "answer_type": "ABSTAIN",
            "abstain_reason": "POLICY_PENDING_HIDDEN_CONTENT",
            "citations": [],
            "unsupported_claims": [],
            "llm_keyword_echo_only": False,
            "llm_gold_leakage_suspected": False,
        },
    ]
    role_rows = [
        {
            "query_id": "q_keyword",
            "expected_answer_text_role": "ENTITY_ANCHOR",
            "must_contain_terms_roles": [
                {"term": "GOLD_ONLY_TERM", "role": "REQUIRED_TARGET_VALUE"},
                {"term": "ridership", "role": "REQUIRED_HEADER_ANCHOR"},
            ],
            "human_review_required": False,
            "rationale": "expected text looks anchor-like",
            "gold_intent_probe_used_for_scoring": False,
            "promotion_evidence": False,
            "answer_evidence_updated": False,
        },
        {
            "query_id": "q_policy",
            "expected_answer_text_role": "POLICY_OR_REVIEW_PLACEHOLDER",
            "must_contain_terms_roles": [{"term": "hidden", "role": "POLICY_GUARDRAIL_TERM"}],
            "human_review_required": True,
            "rationale": "policy placeholder",
            "gold_intent_probe_used_for_scoring": False,
            "promotion_evidence": False,
            "answer_evidence_updated": False,
        },
    ]

    write_jsonl(answer_generation_inputs, source_rows)
    write_jsonl(evidence_objects, evidence_rows)
    write_jsonl(compiled_answers, compiled_rows)
    write_jsonl(source_artifact_dir / "llm_answer_probe_inputs.jsonl", probe_inputs)
    write_jsonl(source_artifact_dir / "llm_answer_probe_outputs.jsonl", probe_outputs)
    write_jsonl(source_artifact_dir / "gold_intent_role_probe.jsonl", role_rows)
    write_role_csv(source_artifact_dir / "gold_intent_role_probe.csv", role_rows)
    write_json(source_artifact_dir / "manifest.json", {"source_inputs": source_input_manifest(source_inputs_dir)})
    write_json(
        source_artifact_dir / "llm_answer_probe_report.json",
        {
            "answer_allowed_xlsx_rows": 1,
            "llm_answer_count": 1,
            "llm_abstain_count": 1,
            "official_xlsx_answer_eval_denominator": 0,
            "promotion_evidence": False,
            "external_live_llm_run": False,
            "llm_model": "fixture-local",
        },
    )
    gold_file = tmp_path / "existing_gold.csv"
    gold_file.write_text("query_id,expected_answer_text\nold,keep\n", encoding="utf-8")
    return {"source_artifact_dir": source_artifact_dir, "gold_file": gold_file}


def source_input_manifest(source_inputs_dir: Path) -> dict[str, dict[str, str]]:
    return {
        "answer_generation_inputs": {"path": str(source_inputs_dir / "answer_generation_inputs.jsonl")},
        "evidence_objects": {"path": str(source_inputs_dir / "evidence_objects.jsonl")},
        "compiled_answers": {"path": str(source_inputs_dir / "compiled_answers.jsonl")},
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_role_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "expected_answer_text_role", "human_review_required", "rationale"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
