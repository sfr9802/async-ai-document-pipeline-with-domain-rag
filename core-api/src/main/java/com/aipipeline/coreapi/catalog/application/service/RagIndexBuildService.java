package com.aipipeline.coreapi.catalog.application.service;

import com.aipipeline.coreapi.catalog.adapter.out.persistence.EvalResultJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.EvalResultJpaRepository;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.IndexBuildJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.IndexBuildJpaRepository;
import com.aipipeline.coreapi.catalog.domain.EvalResultStatus;
import com.aipipeline.coreapi.catalog.domain.IndexBuildStatus;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class RagIndexBuildService {

    private final IndexBuildJpaRepository indexBuilds;
    private final EvalResultJpaRepository evalResults;
    private final ObjectMapper objectMapper;

    @Autowired
    public RagIndexBuildService(IndexBuildJpaRepository indexBuilds,
                                EvalResultJpaRepository evalResults,
                                ObjectMapper objectMapper) {
        this.indexBuilds = indexBuilds;
        this.evalResults = evalResults;
        this.objectMapper = objectMapper == null ? new ObjectMapper() : objectMapper;
    }

    RagIndexBuildService(IndexBuildJpaRepository indexBuilds,
                         EvalResultJpaRepository evalResults) {
        this(indexBuilds, evalResults, new ObjectMapper());
    }

    @Transactional
    public IndexBuildJpaEntity createIndexBuild(CreateIndexBuildCommand command, Instant now) {
        CreateIndexBuildCommand safeCommand = command == null ? CreateIndexBuildCommand.empty() : command;
        if (safeCommand.indexVersion() != null
                && !safeCommand.indexVersion().isBlank()
                && safeCommand.candidateIndexVersion() != null
                && !safeCommand.candidateIndexVersion().isBlank()
                && !safeCommand.indexVersion().equals(safeCommand.candidateIndexVersion())) {
            throw new IllegalArgumentException("indexVersion and candidateIndexVersion must match");
        }
        String generated = "candidate-" + UUID.randomUUID();
        String candidateIndexVersion = firstNonBlank(
                safeCommand.candidateIndexVersion(),
                safeCommand.indexVersion(),
                generated);
        String indexVersion = firstNonBlank(safeCommand.indexVersion(), candidateIndexVersion);
        String id = firstNonBlank(safeCommand.id(), indexVersion);
        if (indexBuilds.existsById(id)) {
            throw new IllegalArgumentException("index build already exists: " + id);
        }
        if (indexBuilds.existsByIndexVersion(indexVersion)) {
            throw new IllegalArgumentException("index version already exists: " + indexVersion);
        }

        return indexBuilds.save(new IndexBuildJpaEntity(
                id,
                indexVersion,
                candidateIndexVersion,
                blankToNull(safeCommand.previousIndexVersion()),
                IndexBuildStatus.CREATED,
                false,
                defaultJsonObject(safeCommand.parserVersionsJson()),
                safeCommand.chunkCount() == null ? 0 : safeCommand.chunkCount(),
                blankToNull(safeCommand.qualityGateJson()),
                null,
                "[]",
                null,
                null,
                null,
                now,
                now));
    }

    @Transactional(readOnly = true)
    public Optional<IndexBuildJpaEntity> findIndexBuild(String id) {
        return indexBuilds.findById(id);
    }

    @Transactional
    public IndexBuildJpaEntity attachEvalResult(String id, String evalResultId, Instant now) {
        if (evalResultId == null || evalResultId.isBlank()) {
            throw new IllegalArgumentException("evalResultId must not be blank");
        }
        IndexBuildJpaEntity build = findRequiredIndexBuild(id);
        EvalResultJpaEntity evalResult = evalResults.findById(evalResultId)
                .orElseThrow(() -> new IllegalArgumentException("Unknown evalResultId: " + evalResultId));
        requireEvalResultMatchesBuild(build, evalResult);
        IndexBuildStatus nextStatus = evalResult.effectiveStatus() == EvalResultStatus.PASSED
                ? IndexBuildStatus.EVAL_PASSED
                : IndexBuildStatus.EVAL_FAILED;
        build.attachEvalResult(evalResult.getId(), nextStatus, now);
        return indexBuilds.save(build);
    }

    @Transactional
    public IndexBuildJpaEntity promote(String id, Instant now) {
        IndexBuildJpaEntity build = findRequiredIndexBuild(id);
        if (build.getStatus() != IndexBuildStatus.EVAL_PASSED) {
            throw new IllegalStateException("index build must be EVAL_PASSED before promotion");
        }
        String evalResultId = build.getEvalResultId();
        if (evalResultId == null || evalResultId.isBlank()) {
            throw new IllegalStateException("index build has no eval result");
        }
        EvalResultJpaEntity evalResult = evalResults.findById(evalResultId)
                .orElseThrow(() -> new IllegalStateException("index build eval result is missing"));
        requireEvalResultMatchesBuild(build, evalResult);
        if (evalResult.effectiveStatus() != EvalResultStatus.PASSED) {
            throw new IllegalStateException("index build eval result must be PASSED before promotion");
        }
        requirePromotionContractClear(build, evalResult);

        Optional<IndexBuildJpaEntity> activeBuild = indexBuilds.findFirstByActiveTrue()
                .filter(active -> !active.getId().equals(build.getId()));
        String previousIndexVersion = activeBuild
                .map(IndexBuildJpaEntity::getIndexVersion)
                .orElse(build.getPreviousIndexVersion());
        activeBuild.ifPresent(active -> {
            active.deactivate(now);
            indexBuilds.save(active);
        });

        build.markPromoted(previousIndexVersion, now);
        return indexBuilds.save(build);
    }

    @Transactional
    public IndexBuildJpaEntity rollback(String id, RollbackIndexBuildCommand command, Instant now) {
        IndexBuildJpaEntity build = findRequiredIndexBuild(id);
        RollbackIndexBuildCommand safeCommand = command == null ? RollbackIndexBuildCommand.empty() : command;
        String currentIndexVersion = firstNonBlank(
                safeCommand.currentIndexVersion(),
                build.getCandidateIndexVersion(),
                build.getIndexVersion());
        String previousIndexVersion = firstNonBlank(
                safeCommand.previousIndexVersion(),
                build.getPreviousIndexVersion());
        build.markRolledBack(currentIndexVersion, previousIndexVersion, now);
        return indexBuilds.save(build);
    }

    private IndexBuildJpaEntity findRequiredIndexBuild(String id) {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("index build id must not be blank");
        }
        return indexBuilds.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Unknown index build id: " + id));
    }

    private static String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String defaultJsonObject(String value) {
        return value == null || value.isBlank() ? "{}" : value;
    }

    private static void requireEvalResultMatchesBuild(IndexBuildJpaEntity build, EvalResultJpaEntity evalResult) {
        if (!equalsNonBlank(evalResult.getIndexVersion(), build.getIndexVersion())) {
            throw new IllegalStateException("eval result index version must match index build");
        }
        if (!equalsNonBlank(evalResult.getCandidateIndexVersion(), build.getCandidateIndexVersion())) {
            throw new IllegalStateException("eval result candidate index version must match index build");
        }
    }

    private void requirePromotionContractClear(IndexBuildJpaEntity build, EvalResultJpaEntity evalResult) {
        JsonNode metrics = readJsonObject(evalResult.getMetricsJson(), "eval metrics_json");
        JsonNode failures = readJson(evalResult.getFailureReasonJson(), "eval failure_reason_json");
        List<String> blockers = new ArrayList<>();
        addRequiredZeroCounterBlocker(blockers, metrics, "gate_input_missing_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "required_index_version_mismatch_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "embedding_status_mismatch_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "candidate_index_mismatch_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "indexing_filtered_hit_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "hidden_content_leakage_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "fatal_warning_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "missing_embedding_record_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "missing_ragmeta_chunk_count");
        addRequiredZeroCounterBlocker(blockers, metrics, "embedding_text_sha256_mismatch_count");
        addThresholdBlocker(blockers, metrics, "unsupported_file_rate", 0.0);
        addThresholdBlocker(blockers, metrics, "parsing_latency_p95_seconds", 30.0);
        if (metrics.path("candidate_snapshot_baseline").asBoolean(false)
                || metrics.path("candidate_snapshot").asBoolean(false)) {
            blockers.add("candidate snapshot baseline cannot be promoted");
        }
        String retrievalBackend = text(metrics, "retrieval_backend");
        if (!"vector".equals(retrievalBackend)) {
            blockers.add("retrieval_backend must be vector before promotion");
        }
        String requiredEmbeddingStatus = text(metrics, "required_embedding_status");
        if (!"EMBEDDED".equals(requiredEmbeddingStatus)) {
            blockers.add("required_embedding_status must be EMBEDDED");
        }
        String requiredIndexVersion = text(metrics, "required_index_version");
        if (!equalsNonBlank(requiredIndexVersion, build.getCandidateIndexVersion())) {
            blockers.add("required_index_version must match index build candidate version");
        }
        if (!equalsNonBlank(text(metrics, "candidate_index_version"), build.getCandidateIndexVersion())
                && metrics.hasNonNull("candidate_index_version")) {
            blockers.add("metrics candidate_index_version must match index build");
        }
        if (!equalsNonBlank(text(metrics, "index_version"), build.getIndexVersion())
                && metrics.hasNonNull("index_version")) {
            blockers.add("metrics index_version must match index build");
        }
        if (isBlank(text(metrics, "immutable_baseline_report_hash"))) {
            blockers.add("immutable baseline report hash is required");
        }
        if (isBlank(text(metrics, "baseline_provenance"))) {
            blockers.add("baseline provenance is required");
        }
        if (isBlank(text(metrics, "baseline_dataset_version"))
                && isBlank(text(metrics, "gold_dataset_version"))
                && isBlank(text(metrics, "eval_dataset_version"))) {
            blockers.add("baseline dataset version is required");
        }
        if (hasFailurePayload(failures)) {
            blockers.add("eval failure_reason_json must be empty before promotion");
        }
        if (!blockers.isEmpty()) {
            throw new IllegalStateException("promotion hard-blocked: " + String.join("; ", blockers));
        }
    }

    private JsonNode readJsonObject(String json, String label) {
        JsonNode node = readJson(json, label);
        if (!node.isObject()) {
            throw new IllegalStateException(label + " must be a JSON object");
        }
        return node;
    }

    private JsonNode readJson(String json, String label) {
        try {
            if (json == null || json.isBlank()) {
                return objectMapper.getNodeFactory().missingNode();
            }
            return objectMapper.readTree(json);
        } catch (IOException | RuntimeException ex) {
            throw new IllegalStateException(label + " is not valid JSON", ex);
        }
    }

    private static void addRequiredZeroCounterBlocker(List<String> blockers, JsonNode metrics, String key) {
        JsonNode node = metrics.path(key);
        if (!node.isNumber()) {
            blockers.add(key + " is required");
        } else if (node.asLong() > 0L) {
            blockers.add(key + " must be zero");
        }
    }

    private static void addThresholdBlocker(List<String> blockers, JsonNode metrics, String key, double threshold) {
        JsonNode node = metrics.path(key);
        if (node.isNumber() && node.asDouble() > threshold) {
            blockers.add(key + " exceeds threshold " + threshold);
        }
    }

    private static String text(JsonNode node, String key) {
        JsonNode value = node.path(key);
        return value.isMissingNode() || value.isNull() ? null : value.asText();
    }

    private static boolean hasFailurePayload(JsonNode failures) {
        if (failures == null || failures.isMissingNode() || failures.isNull()) {
            return false;
        }
        if (failures.isArray()) {
            return !failures.isEmpty();
        }
        if (!failures.isObject()) {
            return false;
        }
        JsonNode metricFailures = failures.path("metric_threshold_failures");
        if (metricFailures.isArray() && !metricFailures.isEmpty()) {
            return true;
        }
        JsonNode bucketFailures = failures.path("bucket_level_failures");
        if (bucketFailures.isArray() && !bucketFailures.isEmpty()) {
            return true;
        }
        JsonNode distribution = failures.path("failure_reason_distribution");
        if (distribution.isObject()) {
            JsonNode overall = distribution.path("overall");
            if (overall.isObject() && overall.fields().hasNext()) {
                return true;
            }
            JsonNode byBucket = distribution.path("by_bucket");
            if (byBucket.isObject() && byBucket.fields().hasNext()) {
                return true;
            }
        }
        return false;
    }

    private static boolean equalsNonBlank(String left, String right) {
        return left != null && !left.isBlank() && left.equals(right);
    }

    public record CreateIndexBuildCommand(
            String id,
            String indexVersion,
            String candidateIndexVersion,
            String previousIndexVersion,
            String parserVersionsJson,
            Integer chunkCount,
            String qualityGateJson
    ) {
        static CreateIndexBuildCommand empty() {
            return new CreateIndexBuildCommand(null, null, null, null, null, null, null);
        }
    }

    public record RollbackIndexBuildCommand(
            String currentIndexVersion,
            String previousIndexVersion
    ) {
        static RollbackIndexBuildCommand empty() {
            return new RollbackIndexBuildCommand(null, null);
        }
    }
}
