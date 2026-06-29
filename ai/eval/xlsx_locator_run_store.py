from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


XLSX_LOCATOR_RUN_STORE_BACKEND = "repo_local_sqlite"
XLSX_LOCATOR_RUN_STORE_FILENAME = "run.sqlite"
XLSX_LOCATOR_RUN_STORE_TABLES = (
    "runs",
    "items",
    "retrieved_contexts",
    "selected_evidence",
    "tool_invocations",
    "tool_candidates",
    "gate_results",
    "residuals",
    "guardrails",
)
XLSX_LOCATOR_TOOL_POLICY = "source_owned_locator_only_no_raw_xlsx_query_time_parsing"
XLSX_LOCATOR_TOOL_OUTPUT_POLICY = "selected_evidence_candidate_must_pass_unchanged_gate"

@dataclass(frozen=True)
class XlsxLocatorToolUseRecord:
    item_index: int
    item_id: str
    execution_status: str
    candidate_count: int
    accepted_candidate_count: int
    source_family_hint: str = ""
    query_task: str = ""
    before_gate_status: str = ""
    after_gate_status: str = ""
    before_residual_class: str = ""
    after_residual_class: str = ""
    candidate_pool_count_before_budget: int = 0
    complete_validated_axis_candidate_count: int = 0
    validated_axis_split_across_candidates: bool = False
    source_row_context_candidate_count: int = 0
    source_row_context_doc_identity_mismatch_candidate_count: int = 0
    source_row_context_blocked_by_doc_identity_mismatch: bool = False
    best_candidate_missing_validated_required_axes: tuple[str, ...] = ()
    matched_query_anchors: tuple[str, ...] = ()
    remaining_missing_query_anchors: tuple[str, ...] = ()
    matched_validated_required_axes: tuple[str, ...] = ()
    remaining_missing_validated_required_axes: tuple[str, ...] = ()
    input_policy: str = XLSX_LOCATOR_TOOL_POLICY
    output_policy: str = XLSX_LOCATOR_TOOL_OUTPUT_POLICY


@dataclass(frozen=True)
class XlsxLocatorEvidenceCandidateRecord:
    item_index: int
    candidate_index: int
    source_family: str
    tool_name: str
    tool_policy: str
    source_atom_id: str
    evidence_bundle_id: str
    doc_id: str
    sheet: str
    cell_range: str
    cell: str = ""
    row_index_1based: str = ""
    row_label: str = ""
    column_label: str = ""
    target_column: str = ""
    header: str = ""
    header_path: str = ""
    table_id: str = ""
    synthetic_table_id: str = ""
    display_value: str = ""
    source_row_context_source_atom_id: str = ""
    source_row_context_doc_id: str = ""
    source_date_aliases: tuple[str, ...] = ()
    locator_text_source: str = ""
    matched_query_anchors: tuple[str, ...] = ()
    missing_query_anchors_after_tool: tuple[str, ...] = ()
    matched_validated_required_axes: tuple[str, ...] = ()
    missing_validated_required_axes: tuple[str, ...] = ()
    confidence_tier: str = "low"
    accepted_for_regating: bool = False
    rejection_reason: str = ""
    input_fields_used: tuple[str, ...] = ()


@dataclass(frozen=True)
class XlsxLocatorGateDeltaRecord:
    before_gate: Mapping[str, Any] = field(default_factory=dict)
    after_gate: Mapping[str, Any] = field(default_factory=dict)
    gate_delta: Mapping[str, Any] = field(default_factory=dict)
    residual_before: Mapping[str, Any] = field(default_factory=dict)
    residual_after: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class XlsxLocatorGuardrailRecord:
    forbidden_input_fields_seen: tuple[str, ...] = ()
    forbidden_input_fields_used: tuple[str, ...] = ()
    forbidden_input_fields_rejected: tuple[str, ...] = ()
    raw_xlsx_query_time_parsing_used: bool = False
    gold_or_qrels_or_label_or_expected_used: bool = False
    retrieved_context_only_citation_promoted: bool = False
    evidence_gate_loosened: bool = False
    report_only_diagnostic: bool = True
    official_metric: bool = False
    official_metric_input_rows: int = 0
    official_metric_input_rows_created: int = 0
    official_metric_input_rows_consumed: int = 0


@dataclass(frozen=True)
class XlsxLocatorRunRecord:
    schema_version: str
    enabled: bool
    report_only_diagnostic: bool
    official_metric: bool
    tool_name: str
    eligible_failed_row_count: int
    tool_invocation_count: int
    accepted_candidate_count: int
    rejected_candidate_count: int
    gate_delta_record: XlsxLocatorGateDeltaRecord
    guardrail_record: XlsxLocatorGuardrailRecord
    anchor_classifier_model: str = ""
    anchor_classifier_prompt_version: str = ""
    anchor_classifier_raw_payload_written: bool = False
    required_anchor_summary: Mapping[str, Any] = field(default_factory=dict)
    query_planner_summary: Mapping[str, Any] = field(default_factory=dict)
    tool_uses: tuple[XlsxLocatorToolUseRecord, ...] = ()
    candidates: tuple[XlsxLocatorEvidenceCandidateRecord, ...] = ()



@dataclass(frozen=True)
class XlsxLocatorRunStoreDependencies:
    clean: Callable[[Any], str]
    as_list: Callable[[Any], list[Any]]
    jsonable: Callable[[Any], Any]
    sha256_text: Callable[[Any], str]
    gate_row_text: Callable[[Mapping[str, Any]], str]
    classify_xlsx_pdf_residual_row: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    query_evidence_item_projection: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    xlsx_locator_candidate_text: Callable[[Mapping[str, Any]], tuple[str, str, Any]]
    xlsx_locator_source_owned_value: Callable[[Mapping[str, Any], str], str]
    internal_xlsx_locator_source_contexts_key: str
    xlsx_locator_source_owned_fields: tuple[str, ...]
    schema_version: str
    evidence_gate_validator_version: str
    run_store_backend: str = XLSX_LOCATOR_RUN_STORE_BACKEND


def _sqlite_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def _report_item_id(
    dependencies: XlsxLocatorRunStoreDependencies,
    row: Mapping[str, Any],
    item_index: int,
) -> str:
    return dependencies.clean(row.get("id") or row.get("item_id") or row.get("query_id")) or str(item_index)


class XlsxLocatorRunStore:
    """Repo-local SQLite store for execute-once XLSX locator diagnostics."""

    def __init__(self, path: Path | str, *, dependencies: XlsxLocatorRunStoreDependencies) -> None:
        self.path = Path(path)
        self._dependencies = dependencies

    def _sqlite_json(self, value: Any) -> str:
        return json.dumps(self._dependencies.jsonable(value), ensure_ascii=False, sort_keys=True)

    def write_run_record(
        self,
        *,
        run_id: str,
        dataset_slug: str,
        collection: str,
        record: XlsxLocatorRunRecord,
        before_rows: Sequence[Mapping[str, Any]],
        after_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        conn = sqlite3.connect(self.path)
        try:
            self._create_schema(conn)
            self._insert_run(
                conn,
                run_id=run_id,
                dataset_slug=dataset_slug,
                collection=collection,
                record=record,
            )
            self._insert_items(conn, before_rows=before_rows, after_rows=after_rows)
            self._insert_contexts(conn, before_rows=before_rows)
            self._insert_selected_evidence(conn, after_rows=after_rows)
            self._insert_tool_invocations(conn, record=record)
            self._insert_tool_candidates(conn, record=record)
            self._insert_gate_results(conn, before_rows=before_rows, after_rows=after_rows)
            self._insert_residuals(conn, before_rows=before_rows, after_rows=after_rows)
            self._insert_guardrails(conn, record=record)
            conn.commit()
        finally:
            conn.close()

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                dataset_slug TEXT NOT NULL,
                collection TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                schema_versions_json TEXT NOT NULL,
                backend TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                report_only_diagnostic INTEGER NOT NULL,
                official_metric INTEGER NOT NULL,
                official_metric_input_rows INTEGER NOT NULL,
                anchor_classifier_model TEXT NOT NULL,
                anchor_classifier_prompt_version TEXT NOT NULL,
                anchor_classifier_raw_payload_written INTEGER NOT NULL,
                required_anchor_summary_json TEXT NOT NULL,
                query_planner_summary_json TEXT NOT NULL,
                guardrail_summary_json TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE items (
                item_index INTEGER PRIMARY KEY,
                item_id TEXT NOT NULL,
                source_family TEXT NOT NULL,
                source_family_hint TEXT NOT NULL,
                query_task TEXT NOT NULL,
                planner_status TEXT NOT NULL,
                row_filters_json TEXT NOT NULL,
                target_axis_json TEXT NOT NULL,
                validated_required_axes_json TEXT NOT NULL,
                before_gate_status TEXT NOT NULL,
                after_gate_status TEXT NOT NULL,
                before_residual_class TEXT NOT NULL,
                after_residual_class TEXT NOT NULL
            );
            CREATE TABLE retrieved_contexts (
                item_index INTEGER NOT NULL,
                context_index INTEGER NOT NULL,
                source_family TEXT NOT NULL,
                source_atom_id TEXT NOT NULL,
                evidence_bundle_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                sheet TEXT NOT NULL,
                cell_range TEXT NOT NULL,
                cell TEXT NOT NULL,
                row_index_1based TEXT NOT NULL,
                row_label TEXT NOT NULL,
                column_label TEXT NOT NULL,
                target_column TEXT NOT NULL,
                header_path TEXT NOT NULL,
                table_id TEXT NOT NULL,
                display_value TEXT NOT NULL,
                rank TEXT NOT NULL,
                text_sha256 TEXT NOT NULL,
                locator_text_sha256 TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (item_index, context_index)
            );
            CREATE TABLE selected_evidence (
                item_index INTEGER NOT NULL,
                evidence_index INTEGER NOT NULL,
                source_family TEXT NOT NULL,
                source_atom_id TEXT NOT NULL,
                evidence_bundle_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                sheet TEXT NOT NULL,
                cell_range TEXT NOT NULL,
                cell TEXT NOT NULL,
                row_index_1based TEXT NOT NULL,
                row_label TEXT NOT NULL,
                column_label TEXT NOT NULL,
                target_column TEXT NOT NULL,
                header_path TEXT NOT NULL,
                table_id TEXT NOT NULL,
                display_value TEXT NOT NULL,
                source_row_context_source_atom_id TEXT NOT NULL,
                source_row_context_doc_id TEXT NOT NULL,
                matched_query_anchors_json TEXT NOT NULL,
                citation_eligible INTEGER NOT NULL,
                PRIMARY KEY (item_index, evidence_index)
            );
            CREATE TABLE tool_invocations (
                item_index INTEGER PRIMARY KEY,
                item_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                candidate_count INTEGER NOT NULL,
                accepted_candidate_count INTEGER NOT NULL,
                complete_validated_axis_candidate_count INTEGER NOT NULL,
                validated_axis_split_across_candidates INTEGER NOT NULL,
                source_row_context_candidate_count INTEGER NOT NULL,
                source_row_context_doc_identity_mismatch_candidate_count INTEGER NOT NULL,
                source_row_context_blocked_by_doc_identity_mismatch INTEGER NOT NULL,
                best_candidate_missing_validated_required_axes_json TEXT NOT NULL,
                matched_query_anchors_json TEXT NOT NULL,
                remaining_missing_query_anchors_json TEXT NOT NULL,
                matched_validated_required_axes_json TEXT NOT NULL,
                remaining_missing_validated_required_axes_json TEXT NOT NULL,
                input_policy TEXT NOT NULL,
                output_policy TEXT NOT NULL
            );
            CREATE TABLE tool_candidates (
                item_index INTEGER NOT NULL,
                candidate_index INTEGER NOT NULL,
                source_family TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_policy TEXT NOT NULL,
                source_atom_id TEXT NOT NULL,
                evidence_bundle_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                sheet TEXT NOT NULL,
                cell_range TEXT NOT NULL,
                cell TEXT NOT NULL,
                row_index_1based TEXT NOT NULL,
                row_label TEXT NOT NULL,
                column_label TEXT NOT NULL,
                target_column TEXT NOT NULL,
                header TEXT NOT NULL,
                header_path TEXT NOT NULL,
                table_id TEXT NOT NULL,
                synthetic_table_id TEXT NOT NULL,
                display_value TEXT NOT NULL,
                source_row_context_source_atom_id TEXT NOT NULL,
                source_row_context_doc_id TEXT NOT NULL,
                source_date_aliases_json TEXT NOT NULL,
                locator_text_source TEXT NOT NULL,
                matched_query_anchors_json TEXT NOT NULL,
                missing_query_anchors_after_tool_json TEXT NOT NULL,
                matched_validated_required_axes_json TEXT NOT NULL,
                missing_validated_required_axes_json TEXT NOT NULL,
                confidence_tier TEXT NOT NULL,
                accepted_for_regating INTEGER NOT NULL,
                rejection_reason TEXT NOT NULL,
                input_fields_used_json TEXT NOT NULL,
                PRIMARY KEY (item_index, candidate_index)
            );
            CREATE TABLE gate_results (
                item_index INTEGER NOT NULL,
                phase TEXT NOT NULL,
                answer_gate_decision TEXT NOT NULL,
                evidence_package_status TEXT NOT NULL,
                gate_json TEXT NOT NULL,
                PRIMARY KEY (item_index, phase)
            );
            CREATE TABLE residuals (
                item_index INTEGER NOT NULL,
                phase TEXT NOT NULL,
                classification TEXT NOT NULL,
                source_family TEXT NOT NULL,
                missing_axis_fields_json TEXT NOT NULL,
                residual_json TEXT NOT NULL,
                PRIMARY KEY (item_index, phase)
            );
            CREATE TABLE guardrails (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            """
        )

    def _insert_run(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        dataset_slug: str,
        collection: str,
        record: XlsxLocatorRunRecord,
    ) -> None:
        schema_versions = {
            "actual_rag_eval": self._dependencies.schema_version,
            "evidence_gate": self._dependencies.evidence_gate_validator_version,
            "xlsx_locator_tool_execute_once": record.schema_version,
        }
        guardrail_summary = asdict(record.guardrail_record)
        conn.execute(
            """
            INSERT INTO runs (
                run_id,
                dataset_slug,
                collection,
                schema_version,
                schema_versions_json,
                backend,
                tool_name,
                enabled,
                report_only_diagnostic,
                official_metric,
                official_metric_input_rows,
                anchor_classifier_model,
                anchor_classifier_prompt_version,
                anchor_classifier_raw_payload_written,
                required_anchor_summary_json,
                query_planner_summary_json,
                guardrail_summary_json,
                record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                dataset_slug,
                collection,
                record.schema_version,
                self._sqlite_json(schema_versions),
                self._dependencies.run_store_backend,
                record.tool_name,
                _sqlite_bool(record.enabled),
                _sqlite_bool(record.report_only_diagnostic),
                _sqlite_bool(record.official_metric),
                int(record.guardrail_record.official_metric_input_rows),
                record.anchor_classifier_model,
                record.anchor_classifier_prompt_version,
                _sqlite_bool(record.anchor_classifier_raw_payload_written),
                self._sqlite_json(record.required_anchor_summary),
                self._sqlite_json(record.query_planner_summary),
                self._sqlite_json(guardrail_summary),
                self._sqlite_json(asdict(record)),
            ),
        )

    def _insert_items(
        self,
        conn: sqlite3.Connection,
        *,
        before_rows: Sequence[Mapping[str, Any]],
        after_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        for item_index, before in enumerate(before_rows):
            after = after_rows[item_index] if item_index < len(after_rows) else {}
            before_residual = self._dependencies.classify_xlsx_pdf_residual_row(before)
            after_residual = self._dependencies.classify_xlsx_pdf_residual_row(after) if isinstance(after, Mapping) else {}
            before_gate = before.get("evidence_gate") if isinstance(before.get("evidence_gate"), Mapping) else {}
            after_gate = after.get("evidence_gate") if isinstance(after.get("evidence_gate"), Mapping) else {}
            planner_projection = self._dependencies.query_evidence_item_projection(before)
            conn.execute(
                """
                INSERT INTO items (
                    item_index,
                    item_id,
                    source_family,
                    source_family_hint,
                    query_task,
                    planner_status,
                    row_filters_json,
                    target_axis_json,
                    validated_required_axes_json,
                    before_gate_status,
                    after_gate_status,
                    before_residual_class,
                    after_residual_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_index,
                    _report_item_id(self._dependencies, before, item_index),
                    self._dependencies.clean(before_residual.get("source_family")) or self._dependencies.clean(after_residual.get("source_family")),
                    self._dependencies.clean(planner_projection.get("source_family_hint")),
                    self._dependencies.clean(planner_projection.get("query_task")),
                    self._dependencies.clean(planner_projection.get("planner_status")),
                    self._sqlite_json(planner_projection.get("row_filters") or {}),
                    self._sqlite_json(planner_projection.get("target_axis") or {}),
                    self._sqlite_json(planner_projection.get("validated_required_axes") or []),
                    self._dependencies.clean(before_gate.get("answer_gate_decision")),
                    self._dependencies.clean(after_gate.get("answer_gate_decision")),
                    self._dependencies.clean(before_residual.get("classification")),
                    self._dependencies.clean(after_residual.get("classification")),
                ),
            )

    def _insert_contexts(self, conn: sqlite3.Connection, *, before_rows: Sequence[Mapping[str, Any]]) -> None:
        for item_index, row in enumerate(before_rows):
            source_contexts = self._dependencies.as_list(row.get(self._dependencies.internal_xlsx_locator_source_contexts_key)) or self._dependencies.as_list(
                row.get("retrieved_contexts")
            )
            for context_index, context in enumerate(source_contexts):
                if not isinstance(context, Mapping):
                    continue
                locator_text, _locator_text_source, _locator_text_fields_used = self._dependencies.xlsx_locator_candidate_text(context)
                conn.execute(
                    """
                    INSERT INTO retrieved_contexts (
                        item_index,
                        context_index,
                        source_family,
                        source_atom_id,
                        evidence_bundle_id,
                        doc_id,
                        sheet,
                        cell_range,
                        cell,
                        row_index_1based,
                        row_label,
                        column_label,
                        target_column,
                        header_path,
                        table_id,
                        display_value,
                        rank,
                        text_sha256,
                        locator_text_sha256,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_index,
                        context_index,
                        self._dependencies.clean(context.get("source_family")),
                        self._dependencies.clean(context.get("source_atom_id")),
                        self._dependencies.clean(context.get("evidence_bundle_id")),
                        self._dependencies.clean(context.get("doc_id")),
                        self._dependencies.xlsx_locator_source_owned_value(context, "sheet"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "cell_range"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "cell"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "row_index_1based"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "row_label"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "column_label"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "target_column"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "header_path"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "table_id"),
                        self._dependencies.xlsx_locator_source_owned_value(context, "display_value"),
                        self._dependencies.clean(context.get("rank")),
                        self._dependencies.sha256_text(self._dependencies.gate_row_text(context)),
                        self._dependencies.sha256_text(locator_text),
                        self._sqlite_json(
                            {
                                field: self._dependencies.xlsx_locator_source_owned_value(context, field)
                                for field in self._dependencies.xlsx_locator_source_owned_fields
                                if self._dependencies.xlsx_locator_source_owned_value(context, field)
                            }
                        ),
                    ),
                )

    def _insert_selected_evidence(self, conn: sqlite3.Connection, *, after_rows: Sequence[Mapping[str, Any]]) -> None:
        for item_index, row in enumerate(after_rows):
            gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
            for evidence_index, evidence in enumerate(self._dependencies.as_list(gate.get("selected_evidence"))):
                if not isinstance(evidence, Mapping):
                    continue
                anchors = sorted(
                    {
                        self._dependencies.clean(anchor)
                        for anchor in self._dependencies.as_list(evidence.get("matched_query_anchors"))
                        if self._dependencies.clean(anchor)
                    }
                )
                conn.execute(
                    """
                    INSERT INTO selected_evidence (
                        item_index,
                        evidence_index,
                        source_family,
                        source_atom_id,
                        evidence_bundle_id,
                        doc_id,
                        tool_name,
                        sheet,
                        cell_range,
                        cell,
                        row_index_1based,
                        row_label,
                        column_label,
                        target_column,
                        header_path,
                        table_id,
                        display_value,
                        source_row_context_source_atom_id,
                        source_row_context_doc_id,
                        matched_query_anchors_json,
                        citation_eligible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_index,
                        evidence_index,
                        self._dependencies.clean(evidence.get("source_family")),
                        self._dependencies.clean(evidence.get("source_atom_id")),
                        self._dependencies.clean(evidence.get("evidence_bundle_id")),
                        self._dependencies.clean(evidence.get("doc_id")),
                        self._dependencies.clean(evidence.get("tool_name")),
                        self._dependencies.clean(evidence.get("sheet")),
                        self._dependencies.clean(evidence.get("cell_range")),
                        self._dependencies.clean(evidence.get("cell")),
                        self._dependencies.clean(evidence.get("row_index_1based")),
                        self._dependencies.clean(evidence.get("row_label")),
                        self._dependencies.clean(evidence.get("column_label")),
                        self._dependencies.clean(evidence.get("target_column")),
                        self._dependencies.clean(evidence.get("header_path")),
                        self._dependencies.clean(evidence.get("table_id")),
                        self._dependencies.clean(evidence.get("display_value")),
                        self._dependencies.clean(evidence.get("source_row_context_source_atom_id")),
                        self._dependencies.clean(evidence.get("source_row_context_doc_id")),
                        self._sqlite_json(anchors),
                        _sqlite_bool(self._dependencies.clean(evidence.get("source_atom_id")) or self._dependencies.clean(evidence.get("evidence_bundle_id"))),
                    ),
                )

    def _insert_tool_invocations(self, conn: sqlite3.Connection, *, record: XlsxLocatorRunRecord) -> None:
        for tool_use in record.tool_uses:
            conn.execute(
                """
                INSERT INTO tool_invocations (
                    item_index,
                    item_id,
                    tool_name,
                    execution_status,
                    candidate_count,
                    accepted_candidate_count,
                    complete_validated_axis_candidate_count,
                    validated_axis_split_across_candidates,
                    source_row_context_candidate_count,
                    source_row_context_doc_identity_mismatch_candidate_count,
                    source_row_context_blocked_by_doc_identity_mismatch,
                    best_candidate_missing_validated_required_axes_json,
                    matched_query_anchors_json,
                    remaining_missing_query_anchors_json,
                    matched_validated_required_axes_json,
                    remaining_missing_validated_required_axes_json,
                    input_policy,
                    output_policy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_use.item_index,
                    tool_use.item_id,
                    record.tool_name,
                    tool_use.execution_status,
                    int(tool_use.candidate_count),
                    int(tool_use.accepted_candidate_count),
                    int(tool_use.complete_validated_axis_candidate_count),
                    _sqlite_bool(tool_use.validated_axis_split_across_candidates),
                    int(tool_use.source_row_context_candidate_count),
                    int(tool_use.source_row_context_doc_identity_mismatch_candidate_count),
                    _sqlite_bool(tool_use.source_row_context_blocked_by_doc_identity_mismatch),
                    self._sqlite_json(tool_use.best_candidate_missing_validated_required_axes),
                    self._sqlite_json(tool_use.matched_query_anchors),
                    self._sqlite_json(tool_use.remaining_missing_query_anchors),
                    self._sqlite_json(tool_use.matched_validated_required_axes),
                    self._sqlite_json(tool_use.remaining_missing_validated_required_axes),
                    tool_use.input_policy,
                    tool_use.output_policy,
                ),
            )

    def _insert_tool_candidates(self, conn: sqlite3.Connection, *, record: XlsxLocatorRunRecord) -> None:
        for candidate in record.candidates:
            conn.execute(
                """
                INSERT INTO tool_candidates (
                    item_index,
                    candidate_index,
                    source_family,
                    tool_name,
                    tool_policy,
                    source_atom_id,
                    evidence_bundle_id,
                    doc_id,
                    sheet,
                    cell_range,
                    cell,
                    row_index_1based,
                    row_label,
                    column_label,
                    target_column,
                    header,
                    header_path,
                    table_id,
                    synthetic_table_id,
                    display_value,
                        source_row_context_source_atom_id,
                        source_row_context_doc_id,
                        source_date_aliases_json,
                        locator_text_source,
                    matched_query_anchors_json,
                    missing_query_anchors_after_tool_json,
                    matched_validated_required_axes_json,
                    missing_validated_required_axes_json,
                    confidence_tier,
                    accepted_for_regating,
                    rejection_reason,
                    input_fields_used_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.item_index,
                    candidate.candidate_index,
                    candidate.source_family,
                    candidate.tool_name,
                    candidate.tool_policy,
                    candidate.source_atom_id,
                    candidate.evidence_bundle_id,
                    candidate.doc_id,
                    candidate.sheet,
                    candidate.cell_range,
                    candidate.cell,
                    candidate.row_index_1based,
                    candidate.row_label,
                    candidate.column_label,
                    candidate.target_column,
                    candidate.header,
                    candidate.header_path,
                    candidate.table_id,
                    candidate.synthetic_table_id,
                    candidate.display_value,
                    candidate.source_row_context_source_atom_id,
                    candidate.source_row_context_doc_id,
                    self._sqlite_json(candidate.source_date_aliases),
                    candidate.locator_text_source,
                    self._sqlite_json(candidate.matched_query_anchors),
                    self._sqlite_json(candidate.missing_query_anchors_after_tool),
                    self._sqlite_json(candidate.matched_validated_required_axes),
                    self._sqlite_json(candidate.missing_validated_required_axes),
                    candidate.confidence_tier,
                    _sqlite_bool(candidate.accepted_for_regating),
                    candidate.rejection_reason,
                    self._sqlite_json(candidate.input_fields_used),
                ),
            )

    def _insert_gate_results(
        self,
        conn: sqlite3.Connection,
        *,
        before_rows: Sequence[Mapping[str, Any]],
        after_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        for phase, rows in (("before", before_rows), ("after", after_rows)):
            for item_index, row in enumerate(rows):
                gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
                conn.execute(
                    """
                    INSERT INTO gate_results (
                        item_index,
                        phase,
                        answer_gate_decision,
                        evidence_package_status,
                        gate_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        item_index,
                        phase,
                        self._dependencies.clean(gate.get("answer_gate_decision")),
                        self._dependencies.clean(gate.get("evidence_package_status")),
                        self._sqlite_json(gate),
                    ),
                )

    def _insert_residuals(
        self,
        conn: sqlite3.Connection,
        *,
        before_rows: Sequence[Mapping[str, Any]],
        after_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        for phase, rows in (("before", before_rows), ("after", after_rows)):
            for item_index, row in enumerate(rows):
                residual = self._dependencies.classify_xlsx_pdf_residual_row(row)
                conn.execute(
                    """
                    INSERT INTO residuals (
                        item_index,
                        phase,
                        classification,
                        source_family,
                        missing_axis_fields_json,
                        residual_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_index,
                        phase,
                        self._dependencies.clean(residual.get("classification")),
                        self._dependencies.clean(residual.get("source_family")),
                        self._sqlite_json(self._dependencies.as_list(residual.get("source_axis_fields_missing"))),
                        self._sqlite_json(residual),
                    ),
                )

    def _insert_guardrails(self, conn: sqlite3.Connection, *, record: XlsxLocatorRunRecord) -> None:
        guardrail_payload = asdict(record.guardrail_record)
        for key, value in guardrail_payload.items():
            conn.execute(
                "INSERT INTO guardrails (key, value_json) VALUES (?, ?)",
                (key, self._sqlite_json(value)),
            )
