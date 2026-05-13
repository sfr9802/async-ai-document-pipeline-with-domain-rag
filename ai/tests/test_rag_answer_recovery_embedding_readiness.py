from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONFIG = ROOT / "eval" / "configs" / "answer_recovery_embedding_readiness.yaml"
REPORT_DIR = ROOT / "eval" / "reports" / "rag-ingestion"

_MODULE = None
_REPORT = None


def test_embedding_readiness_preserves_registry_and_decision_flags():
    module, report = _report()

    assert module.validate_config(module.load_config(CONFIG)) == []
    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert report["decision"]["staging_backfill_performed"] is False
    assert report["official_denominator_registry_diff_proof"]["diff_empty"] is True
    assert report["guardrail_status"]["production_index_mutation"] is False
    assert report["guardrail_status"]["broad_indexing"] is False

    diff = subprocess.run(
        ["git", "diff", "--quiet", "--", "ai/eval/eval_queries/official_denominator_registry.json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert diff.returncode == 0


def test_embedding_readiness_uses_only_safe_diagnostic_namespace():
    module, report = _report()
    backend = report["embedding_backend"]
    inventory = report["namespace_inventory"]
    policy = module.load_config(CONFIG)["embedding_backend"]["namespace_safety"]

    assert backend["staging_namespace"] == "diagnostic_answer_recovery_embedding_readiness_v1"
    assert module.namespace_is_safe(backend["staging_namespace"], policy) is True
    assert module.namespace_is_safe("production_answer_recovery", policy) is False
    assert backend["production_namespace_used"] is False
    assert inventory["production_namespace_used"] is False
    assert backend["embedding_backend_available"] is True
    assert backend["backend_probe_embedding_succeeded"] is True
    assert backend["staging_backfill_enabled_by_config"] is False
    assert backend["staging_backfill_status"] == "skipped_backfill_disabled_by_config"


def test_backfill_disabled_does_not_imply_backend_unavailable():
    module = _load_readiness_script()
    config = _test_config(module)
    config["embedding_backend"]["perform_staging_backfill"] = False
    namespace = _namespace_payload(staging_exists=False)

    backend = module.summarize_embedding_backend(config, namespace, [], **_fake_backend_kwargs())

    assert backend["embedding_backend_available"] is True
    assert backend["backend_probe_embedding_succeeded"] is True
    assert backend["staging_backfill_enabled_by_config"] is False
    assert backend["staging_backfill_status"] == "skipped_backfill_disabled_by_config"


def test_missing_staging_namespace_does_not_imply_backend_unavailable():
    module = _load_readiness_script()
    config = _test_config(module)
    config["embedding_backend"]["perform_staging_backfill"] = True
    namespace = _namespace_payload(staging_exists=False)

    backend = module.summarize_embedding_backend(config, namespace, [], **_fake_backend_kwargs())

    assert backend["embedding_backend_available"] is True
    assert backend["staging_namespace_exists"] is False
    assert backend["staging_backfill_status"] == "skipped_staging_namespace_missing"


def test_vector_write_disabled_does_not_imply_backend_unavailable():
    module = _load_readiness_script()
    config = _test_config(module)
    config["embedding_backend"]["perform_staging_backfill"] = True
    config["embedding_backend"]["allow_vector_write"] = False
    namespace = _namespace_payload(staging_exists=True)

    backend = module.summarize_embedding_backend(config, namespace, [], **_fake_backend_kwargs())

    assert backend["embedding_backend_available"] is True
    assert backend["vector_write_allowed"] is False
    assert backend["staging_backfill_status"] == "skipped_write_not_allowed"


def test_backend_import_or_construction_failure_marks_backend_unavailable():
    module = _load_readiness_script()
    config = _test_config(module)
    namespace = _namespace_payload(staging_exists=True)

    import_failure = module.summarize_embedding_backend(
        config,
        namespace,
        [],
        **{
            **_fake_backend_kwargs(),
            "provider_importer": _raise_provider_import,
        },
    )
    assert import_failure["embedding_backend_available"] is False
    assert "provider import failure" in import_failure["backend_unavailable_reason"]

    construction_failure = module.summarize_embedding_backend(
        config,
        namespace,
        [],
        **{
            **_fake_backend_kwargs(),
            "embedder_factory": _raise_embedder_construction,
        },
    )
    assert construction_failure["embedding_backend_available"] is False
    assert "provider construction failure" in construction_failure["backend_unavailable_reason"]


def test_missing_required_env_reports_redacted_missing_env_reason():
    module = _load_readiness_script()
    config = _test_config(module)
    config["embedding_backend"]["required_env_vars"] = ["AIPIPELINE_WORKER_FAKE_SECRET_TOKEN"]
    config["embedding_backend"]["env_presence_vars"] = ["AIPIPELINE_WORKER_FAKE_SECRET_TOKEN"]
    namespace = _namespace_payload(staging_exists=True)

    backend = module.summarize_embedding_backend(config, namespace, [], **_fake_backend_kwargs(env={}))

    assert backend["embedding_backend_available"] is False
    assert backend["backend_required_env_present"] is False
    assert backend["missing_required_env_vars"] == ["AIPIPELINE_WORKER_FAKE_SECRET_TOKEN"]
    assert "AIPIPELINE_WORKER_FAKE_SECRET_TOKEN" in backend["backend_unavailable_reason"]
    assert "secret-value" not in backend["backend_unavailable_reason"]


def test_successful_fake_backend_probe_sets_dimension_and_never_writes():
    module = _load_readiness_script()
    config = _test_config(module)
    namespace = _namespace_payload(staging_exists=True)
    recorder: dict[str, list[str]] = {}

    backend = module.summarize_embedding_backend(
        config,
        namespace,
        [],
        **_fake_backend_kwargs(recorder=recorder),
    )

    assert backend["embedding_backend_available"] is True
    assert backend["backend_probe_embedding_succeeded"] is True
    assert backend["backend_embedding_dimension_detected"] == 7
    assert backend["vector_write_attempted"] is False
    assert backend["namespace_created"] is False
    assert recorder["queries"] == [module.DIAGNOSTIC_BACKEND_PROBE_TEXT]


def test_diagnostic_probe_text_is_synthetic_not_eval_content():
    module = _load_readiness_script()
    config = _test_config(module)
    namespace = _namespace_payload(staging_exists=True)
    recorder: dict[str, list[str]] = {}

    backend = module.summarize_embedding_backend(
        config,
        namespace,
        [],
        **_fake_backend_kwargs(recorder=recorder),
    )

    probe_text = recorder["queries"][0]
    assert probe_text == "diagnostic embedding backend contract probe"
    assert backend["backend_probe_text_policy"]["derived_from_expected_answers"] is False
    assert backend["backend_probe_text_policy"]["derived_from_labels"] is False
    assert backend["backend_probe_text_policy"]["derived_from_eval_evidence_text"] is False
    forbidden_fragments = ("expected_answer", "label", "evidence", "csv", "gold")
    assert all(fragment not in probe_text.lower() for fragment in forbidden_fragments)


def test_embedding_readiness_blocks_hidden_diagnostic_pdf_file_and_frozen_rows():
    _, report = _report()
    rows = {row["row_id"]: row for row in report["manifest_rows"]}

    hidden = rows["expanded_xlsx_hidden_blocked_001"]
    assert hidden["hidden_xlsx"] is True
    assert hidden["manifest_classification"] == "SKIP_HIDDEN_XLSX"
    assert hidden["support_eligible"] is False

    diagnostic = rows["expanded_ocr_shadow_001"]
    assert diagnostic["diagnostic_only"] is True
    assert diagnostic["manifest_classification"] == "SKIP_DIAGNOSTIC_ONLY_SHADOW"
    assert diagnostic["support_eligible"] is False

    pdf_file = rows["expanded_pdf_file_lookup_007"]
    assert pdf_file["lane"] == "PDF_FILE_LOOKUP"
    assert pdf_file["pdf_file_identity_only"] is True
    assert pdf_file["pdf_file_content_mixing_risk"] is True
    assert pdf_file["manifest_classification"] == "SKIP_PDF_FILE_CONTENT_MIXING_RISK"
    assert pdf_file["support_eligible"] is False

    frozen_rows = [row for row in report["manifest_rows"] if row["frozen_gold_sourced_row"]]
    assert frozen_rows
    assert all(row["selection_or_training_eligible"] is False for row in frozen_rows)
    assert all(row["embedding_eligible"] is False for row in frozen_rows)


def test_embedding_readiness_never_embeds_expected_answers_or_labels():
    _, report = _report()

    assert report["counts"]["expected_answer_or_label_embedding_count"] == 0
    assert report["guardrail_status"]["expected_answer_or_label_embedding_count"] == 0
    assert all(row["expected_answer_or_label_embedded"] is False for row in report["manifest_rows"])
    for row in report["manifest_rows"]:
        if row["manifest_classification"] == "SKIP_EXPECTED_ANSWER_OR_LABEL":
            assert row["support_eligible"] is False
            assert row["embedding_eligible"] is False


def test_embedding_readiness_report_includes_required_category_counts():
    module, report = _report()
    classifications = report["counts"]["classification_counts"]

    for classification in module.CLASSIFICATION_ORDER:
        assert classification in classifications
    assert report["counts"]["manifest_row_count"] == 37
    assert report["counts"]["safe_existing_row_count"] == 5
    assert report["counts"]["index_scope_missing_row_count"] == 5
    assert report["counts"]["classification_counts"]["EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE"] == 5
    assert report["counts"]["hidden_xlsx_support_eligible_count"] == 0
    assert report["counts"]["diagnostic_only_support_eligible_count"] == 0
    assert report["counts"]["pdf_file_content_mixing_support_eligible_count"] == 0


def test_embedding_readiness_index_scope_rows_are_surfaced_with_actions():
    _, report = _report()
    rows = report["index_scope_missing_rows"]
    causes = report["counts"]["index_scope_missing_cause_counts"]

    assert len(rows) == 5
    assert causes["indexing_scope_policy"] == 3
    assert causes["source_is_diagnostic_only"] == 2
    for row in rows:
        assert row["recommended_action"]
        assert row["manifest_classification"] in {"SKIP_POLICY_BLOCKED", "SKIP_DIAGNOSTIC_ONLY_SHADOW"}


def test_embedding_readiness_safe_existing_rows_have_canonical_source_chunks():
    _, report = _report()
    safe_rows = [
        row for row in report["manifest_rows"] if row["triage_category"] == "SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"
    ]

    assert len(safe_rows) == 5
    for row in safe_rows:
        assert row["canonical_source_id"]
        assert row["chunk_id"]
        assert row["source_text_available"] is True
        assert row["already_embedded"] is True
        assert row["embedding_eligible"] is True
        assert row["support_eligible"] is True
        assert row["hidden_xlsx"] is False
        assert row["diagnostic_only"] is False
        assert row["frozen_gold_sourced_row"] is False
        assert row["pdf_file_content_mixing_risk"] is False
        assert row["missing_from_configured_staging_namespace"] is True


def test_embedding_readiness_unknown_rows_are_not_embedded_or_promoted():
    module, _ = _report()
    triage = {
        "row_id": "synthetic_unknown",
        "lane": "TEXT",
        "category": "UNKNOWN_NEEDS_MANUAL_REVIEW",
        "evidence_is_diagnostic_only": False,
        "hidden_xlsx_involved": False,
        "pdf_file_identity_content_mixing_risk": False,
    }
    derived = module.derive_manifest_classification(
        triage=triage,
        expanded={},
        source_record={},
        metadata={"canonical_source_id": "", "chunk_id": ""},
        chunk_lookup={},
        excluded_sources=set(),
    )

    assert derived["classification"] == "SKIP_POLICY_BLOCKED"
    assert derived["skip_reason"] == "current_policy_blocks_support_or_requires_manual_review"


def test_embedding_readiness_script_emits_reports():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rag_answer_recovery_embedding_readiness.py"),
            "--config",
            str(CONFIG),
            "--skip-backend-probe",
            "--artifact-profile",
            "debug",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "staging_backfill_status" in result.stdout
    report = json.loads((REPORT_DIR / "answer_recovery_embedding_readiness.json").read_text(encoding="utf-8"))
    inventory = json.loads(
        (REPORT_DIR / "answer_recovery_embedding_namespace_inventory.json").read_text(encoding="utf-8")
    )
    manifest_lines = (REPORT_DIR / "answer_recovery_embedding_backfill_manifest.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()

    assert report["decision"]["production_promotion_ready"] is False
    assert report["decision"]["official_answer_denominator_ready"] is False
    assert inventory["staging_namespace"] == "diagnostic_answer_recovery_embedding_readiness_v1"
    assert len(manifest_lines) == report["counts"]["manifest_row_count"]


def _report():
    global _MODULE, _REPORT
    if _MODULE is None:
        _MODULE = _load_readiness_script()
    if _REPORT is None:
        config = _MODULE.load_config(CONFIG)
        _REPORT = _MODULE.run_readiness(
            config=config,
            config_path=CONFIG,
            backend_contract_kwargs=_fake_backend_kwargs(),
        )
    return _MODULE, _REPORT


def _load_readiness_script():
    module_path = ROOT / "scripts" / "rag_answer_recovery_embedding_readiness.py"
    spec = importlib.util.spec_from_file_location("rag_answer_recovery_embedding_readiness_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _test_config(module):
    return deepcopy(module.load_config(CONFIG))


def _namespace_payload(*, staging_exists: bool) -> dict:
    return {
        "embedding_backend_config_detected": True,
        "embedding_provider_config_files": [
            "ai/app/core/config.py",
            "ai/app/capabilities/rag/embeddings.py",
        ],
        "vector_index_config_detected": True,
        "vector_index_config_files": ["ai/app/capabilities/rag/faiss_index.py"],
        "index_root": "ai/eval/indexes",
        "index_root_exists": True,
        "existing_namespace_count": 1,
        "namespaces": [{"namespace": "fake-existing", "has_faiss_index": True}],
        "staging_namespace": "diagnostic_answer_recovery_embedding_readiness_v1",
        "staging_namespace_path": "ai/eval/indexes/diagnostic_answer_recovery_embedding_readiness_v1",
        "staging_namespace_safe": True,
        "staging_namespace_exists": staging_exists,
        "production_namespace_used": False,
        "production_index_mutation": False,
    }


def _fake_settings():
    return SimpleNamespace(
        rag_embedding_model="fake-embedding-model",
        rag_embedding_prefix_query="",
        rag_embedding_prefix_passage="",
        rag_embedding_max_seq_length=128,
        rag_embedding_batch_size=4,
        rag_embedding_cuda_alloc_conf="",
        rag_index_dir="eval/indexes/fake",
        rag_embedding_text_variant="retrieval_title_section",
    )


def _fake_provider_importer():
    return object, lambda value: value


class _FakeFaissIndex:
    def load(self):
        return None

    def search(self, query_vectors, top_k):
        return []

    def build(self, vectors, *, index_version, embedding_model):
        return None

    def build_staged(self, vectors, *, index_version, embedding_model):
        return None

    def promote_staged(self, stage_dir, info, *, extra_files=()):
        return None


class _FakeVectors:
    shape = (1, 7)


class _FakeEmbedder:
    dimension = 7
    model_name = "fake-embedding-model"

    def __init__(self, recorder: dict[str, list[str]] | None = None) -> None:
        self._recorder = recorder

    def embed_queries(self, texts):
        if self._recorder is not None:
            self._recorder["queries"] = list(texts)
        return _FakeVectors()


def _fake_embedder_factory(*, recorder: dict[str, list[str]] | None = None):
    def factory(**_kwargs):
        return _FakeEmbedder(recorder)

    return factory


def _fake_backend_kwargs(*, env=None, recorder: dict[str, list[str]] | None = None):
    return {
        "settings_factory": _fake_settings,
        "provider_importer": _fake_provider_importer,
        "vector_importer": lambda: _FakeFaissIndex,
        "embedder_factory": _fake_embedder_factory(recorder=recorder),
        "env": {} if env is None else env,
    }


def _raise_provider_import():
    raise ImportError("missing fake provider")


def _raise_embedder_construction(**_kwargs):
    raise RuntimeError("fake construction failed")
