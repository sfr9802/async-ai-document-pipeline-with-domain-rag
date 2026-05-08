from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AI_WORKER = ROOT / "ai-worker"
MODULE_PATH = AI_WORKER / "eval" / "harness" / "xlsx_silver_generation.py"

REPORT_PATH = AI_WORKER / "eval" / "reports" / "rag-ingestion" / "xlsx_silver_retrieval_evidence_generation_report_20260507.json"
MANIFEST_PATH = AI_WORKER / "eval" / "reports" / "rag-ingestion" / "xlsx_silver_retrieval_evidence_generation_manifest_v0.json"
VALIDATION_PATH = AI_WORKER / "eval" / "reports" / "rag-ingestion" / "xlsx_silver_retrieval_evidence_validation_report_v0.json"
CANDIDATES_CSV = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_candidates_v0.csv"
CANDIDATES_JSONL = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_candidates_v0.jsonl"
SELECTED_CSV = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_selected_v0.csv"
SELECTED_JSONL = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_selected_v0.jsonl"
DEV_CSV = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_dev_v0.csv"
HOLDOUT_CSV = AI_WORKER / "eval" / "eval_queries" / "xlsx_silver_retrieval_evidence_holdout_v0.csv"
OFFICIAL_RETRIEVAL_CSV = AI_WORKER / "eval" / "eval_queries" / "gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
LEGACY_V3_CSV = AI_WORKER / "eval" / "eval_queries" / "gold_queries_xlsx_v3_positive_reviewed.csv"
REGISTRY_PATH = AI_WORKER / "eval" / "eval_queries" / "official_denominator_registry.json"


def load_module():
    if str(AI_WORKER) not in sys.path:
        sys.path.insert(0, str(AI_WORKER))
    scripts_dir = str(AI_WORKER / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("xlsx_silver_generation_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


silver = load_module()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_query(value: str) -> str:
    return re.sub(r"[\s?.!,]+", "", value.strip()).lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def report() -> dict:
    return read_json(REPORT_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return read_json(MANIFEST_PATH)


@pytest.fixture(scope="module")
def validation_report() -> dict:
    return read_json(VALIDATION_PATH)


@pytest.fixture(scope="module")
def selected_rows() -> list[dict[str, str]]:
    return read_csv(SELECTED_CSV)


@pytest.fixture(scope="module")
def candidate_rows() -> list[dict[str, str]]:
    return read_csv(CANDIDATES_CSV)


@pytest.fixture(scope="module")
def dev_rows() -> list[dict[str, str]]:
    return read_csv(DEV_CSV)


@pytest.fixture(scope="module")
def holdout_rows() -> list[dict[str, str]]:
    return read_csv(HOLDOUT_CSV)


def test_xlsx_silver_generation_requires_strict_approval(tmp_path: Path):
    blocked_report = tmp_path / "blocked_pre_silver_report.json"
    blocked_report.write_text(
        json.dumps({"status": "BLOCKED_PENDING_XLSX_SILVER_PRECONDITION_FIXES"}),
        encoding="utf-8",
    )

    with pytest.raises(silver.XlsxPreSilverRiskError, match=silver.STRICT_APPROVAL_STATUS):
        silver.verify_preconditions(pre_silver_report=blocked_report, registry_path=silver.OFFICIAL_REGISTRY)


def test_xlsx_silver_generation_uses_strict_wrapper_only(report: dict):
    wrapper = report["preconditions"]["strict_wrapper"]
    assert wrapper["route"] == "xlsx_human_review_retrieval_projection"
    assert wrapper["namespace"] == "rag-ingestion-v2-xlsx-candidate-v1"
    assert wrapper["positive_gold"].endswith("gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv")
    assert report["route_guard_result"]["strict_wrapper_path_used"] is True


def test_xlsx_silver_generation_disallows_generic_orchestrator(report: dict):
    assert report["route_guard_result"]["generic_agent_orchestrator_used"] is False
    assert report["preconditions"]["strict_wrapper"]["generic_agent_orchestrator_used"] is False


def test_xlsx_silver_generation_disallows_global_namespace(report: dict):
    assert report["route_guard_result"]["global_retriever_used"] is False
    assert report["route_guard_result"]["namespace"] == "rag-ingestion-v2-xlsx-candidate-v1"


def test_xlsx_silver_generation_disallows_text_pdf_namespaces(report: dict):
    assert report["route_guard_result"]["text_pdf_namespace_used"] is False
    assert all("xlsx" in report["route_guard_result"]["namespace"].lower() for _ in [0])


def test_xlsx_silver_rows_are_not_official_denominator(selected_rows: list[dict[str, str]], report: dict):
    assert report["denominator_guard_result"]["silver_rows_in_official_gold_denominator"] == 0
    assert all(not parse_bool(row["include_in_official_gold_denominator"]) for row in selected_rows)
    assert all(not parse_bool(row["include_in_official_positive_denominator"]) for row in selected_rows)


def test_xlsx_silver_rows_are_not_answer_denominator(selected_rows: list[dict[str, str]], report: dict):
    assert report["denominator_guard_result"]["silver_rows_in_answer_generation_denominator"] == 0
    assert all(not parse_bool(row["include_in_answer_generation_denominator"]) for row in selected_rows)
    assert all(parse_bool(row["not_answer_generation_denominator"]) for row in selected_rows)


def test_xlsx_silver_rows_have_promotion_evidence_false(selected_rows: list[dict[str, str]], report: dict):
    assert report["promotion_evidence"] is False
    assert report["denominator_guard_result"]["promotion_evidence_true_rows"] == 0
    assert all(not parse_bool(row["promotion_evidence"]) for row in selected_rows)
    assert all(not parse_bool(row["official_metric_included"]) for row in selected_rows)


def test_xlsx_silver_rows_have_valid_citation_locator(selected_rows: list[dict[str, str]]):
    for row in selected_rows:
        locator = json.loads(row["citation_locator"])
        assert locator["track"] == "XLSX"
        assert locator["source_file_id"] == row["source_file_id"]
        assert locator["search_unit_id"] == row["source_search_unit_id"]
        assert locator["sheet"] == row["sheet"]
        assert locator["range"] == row["range"]
        if row["cell"]:
            assert locator["cell"] == row["cell"]
            assert silver.parse_cell(row["cell"]) is not None
        assert silver.parse_range(row["range"]) is not None


def test_xlsx_silver_rows_preserve_parser_version_location_json_citation_text(selected_rows: list[dict[str, str]]):
    for row in selected_rows:
        location = json.loads(row["location_json"])
        assert row["parser_version"] == "xlsx-extract-v2-hidden-safe"
        assert location["track"] == "XLSX"
        assert location["sheet"] == row["sheet"]
        assert location["range"] == row["range"]
        assert location["parser_version"] == row["parser_version"]
        assert row["citation_text"].strip()


def test_xlsx_silver_rows_exclude_hidden_content(selected_rows: list[dict[str, str]], report: dict):
    blocked_terms = {"hidden_policy_negative", "secret 숨겨진", "숨김 시트"}
    assert report["hidden_content_leakage_result"]["status"] == "PASS_METADATA_ONLY"
    assert report["hidden_content_leakage_result"]["workbook_reopen_probe"] == "not_run"
    assert report["hidden_content_leakage_result"]["hidden_flagged_source_units"] == 0
    for row in selected_rows:
        assert row["hidden_policy"] == "exclude_hidden"
        assert row["hidden_policy_version"] == "exclude-hidden-v1"
        lowered = json.dumps(row, ensure_ascii=False).lower()
        assert not any(term in lowered for term in blocked_terms)


def test_xlsx_silver_rows_have_unique_query_ids(candidate_rows: list[dict[str, str]], selected_rows: list[dict[str, str]]):
    candidate_ids = [row["query_id"] for row in candidate_rows]
    selected_ids = [row["query_id"] for row in selected_rows]
    assert len(candidate_ids) == len(set(candidate_ids))
    assert len(selected_ids) == len(set(selected_ids))
    assert all(query_id.startswith("xlsx_silver_v0_") for query_id in candidate_ids)


def test_xlsx_silver_rows_do_not_collide_with_gold_query_ids(candidate_rows: list[dict[str, str]]):
    candidate_ids = {row["query_id"] for row in candidate_rows}
    official_ids = {row["query_id"] for row in read_csv(OFFICIAL_RETRIEVAL_CSV)}
    legacy_ids = {row["query_id"] for row in read_csv(LEGACY_V3_CSV)}
    assert candidate_ids.isdisjoint(official_ids)
    assert candidate_ids.isdisjoint(legacy_ids)


def test_xlsx_silver_dev_holdout_have_no_query_id_overlap(dev_rows: list[dict[str, str]], holdout_rows: list[dict[str, str]]):
    assert {row["query_id"] for row in dev_rows}.isdisjoint({row["query_id"] for row in holdout_rows})


def test_xlsx_silver_dev_holdout_are_stratified(report: dict, dev_rows: list[dict[str, str]], holdout_rows: list[dict[str, str]]):
    assert len(dev_rows) == 350
    assert len(holdout_rows) == 150
    assert report["split_distribution"]["dev_answer_shape"] == dict(Counter(row["answer_shape"] for row in dev_rows))
    assert report["split_distribution"]["holdout_answer_shape"] == dict(Counter(row["answer_shape"] for row in holdout_rows))
    assert len(holdout_rows) / (len(dev_rows) + len(holdout_rows)) == 0.30
    for shape, total in report["answer_shape_distribution"].items():
        dev_count = report["split_distribution"]["dev_answer_shape"].get(shape, 0)
        holdout_count = report["split_distribution"]["holdout_answer_shape"].get(shape, 0)
        assert dev_count + holdout_count == total
        assert 0.10 <= (holdout_count / total) <= 0.45


def test_xlsx_silver_manifest_hashes_match(manifest: dict):
    for entry in manifest["artifact_hashes"].values():
        path = ROOT / entry["path"]
        assert path.exists(), entry["path"]
        assert sha256_file(path) == entry["sha256"]


def test_current_xlsx_official_denominator_remains_23_after_silver_generation(report: dict):
    assert report["preconditions"]["official_denominator_before"] == 23
    assert report["denominator_guard_result"]["official_xlsx_retrieval_evidence_denominator_after"] == 23
    registry = read_json(REGISTRY_PATH)
    current = registry["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"]
    assert current["official_positive_denominator"] == 23
    assert current["official_positive_retrieval_subset_path"].endswith(
        "gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
    )


def test_xlsx_answer_generation_denominator_remains_zero_after_silver_generation(report: dict):
    assert report["preconditions"]["answer_denominator_before"] == 0
    assert report["denominator_guard_result"]["xlsx_answer_generation_denominator_after"] == 0
    registry = read_json(REGISTRY_PATH)
    current = registry["official_diagnostic_denominators"]["track_a_xlsx_human_review_normalized_v0"]
    assert current["official_xlsx_answer_generation_denominator"] == 0


def test_legacy_xlsx_v3_35_rows_not_used_as_current_silver_source_of_truth(candidate_rows: list[dict[str, str]], report: dict):
    assert report["preconditions"]["current_xlsx_artifacts"]["legacy_v3_superseded"] is True
    assert len(read_csv(LEGACY_V3_CSV)) == 35
    assert {row["source_dataset"] for row in candidate_rows} == {"ragmeta_xlsx_candidate_v1_search_units"}
    assert all("v3" not in row["source_dataset"].lower() for row in candidate_rows)
    assert all("legacy" not in row["source_dataset"].lower() for row in candidate_rows)


def test_xlsx_silver_selected_rows_have_no_duplicate_queries_or_locators(
    selected_rows: list[dict[str, str]],
    report: dict,
):
    queries = [normalize_query(row["query"]) for row in selected_rows]
    locators = [row["citation_locator"] for row in selected_rows]
    assert len(queries) == len(set(queries))
    assert len(locators) == len(set(locators))
    assert report["duplicate_near_duplicate_findings"]["duplicate_query_count"] == 0
    assert report["duplicate_near_duplicate_findings"]["duplicate_locator_count"] == 0
    assert report["query_locator_leakage_result"]["exact_range_or_cell_in_query_count"] == 0
    for row in selected_rows:
        query = row["query"].upper()
        assert row["range"].upper() not in query
        if row["cell"]:
            assert row["cell"].upper() not in query


def test_xlsx_silver_dev_holdout_have_no_source_overlap(
    report: dict,
    dev_rows: list[dict[str, str]],
    holdout_rows: list[dict[str, str]],
):
    overlap_summary = report["duplicate_near_duplicate_findings"]["dev_holdout_source_overlap"]
    assert overlap_summary["status"] == "PASS"
    assert all(count == 0 for count in overlap_summary["overlap_counts"].values())
    for field in ["source_content_sha256", "source_display_text_sha256"]:
        assert {row[field] for row in dev_rows}.isdisjoint({row[field] for row in holdout_rows})
    assert {normalize_query(row["citation_text"]) for row in dev_rows}.isdisjoint(
        {normalize_query(row["citation_text"]) for row in holdout_rows}
    )


def test_xlsx_silver_rows_do_not_use_synthetic_header_labels(selected_rows: list[dict[str, str]], report: dict):
    synthetic = re.compile(r"\b[HC]\d+\b", flags=re.IGNORECASE)
    assert report["rejected_candidate_reason_counts"] == {"synthetic_label_not_source_bound": 3}
    for row in selected_rows:
        assert not synthetic.search(row["query"])
        assert not synthetic.search(row["expected_answer_text"])
        assert not synthetic.search(row["must_contain_terms"])


def test_xlsx_silver_generated_csv_jsonl_schema_matches(
    candidate_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    report: dict,
    validation_report: dict,
):
    candidate_jsonl_rows = read_jsonl(CANDIDATES_JSONL)
    selected_jsonl_rows = read_jsonl(SELECTED_JSONL)
    assert len(candidate_rows) == len(candidate_jsonl_rows) == report["candidate_pool_count"] == 702
    assert len(selected_rows) == len(selected_jsonl_rows) == report["selected_silver_count"] == 500
    assert set(candidate_rows[0]) == set(silver.CANDIDATE_FIELDNAMES)
    assert set(selected_rows[0]) == set(silver.CANDIDATE_FIELDNAMES)
    assert validation_report["status"] == "PASS"
    assert validation_report["rejected_rows_count"] == 3
