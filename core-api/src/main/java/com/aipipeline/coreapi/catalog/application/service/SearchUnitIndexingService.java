package com.aipipeline.coreapi.catalog.application.service;

import com.aipipeline.coreapi.catalog.adapter.out.persistence.ExtractedArtifactJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.ExtractedArtifactJpaRepository;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.EmbeddingRecordJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.EmbeddingRecordJpaRepository;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.SearchUnitJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.SearchUnitJpaRepository;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.SourceFileJpaEntity;
import com.aipipeline.coreapi.catalog.adapter.out.persistence.SourceFileJpaRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

@Service
public class SearchUnitIndexingService {

    public static final String EMBEDDING_STATUS_PENDING = "PENDING";
    public static final String EMBEDDING_STATUS_EMBEDDING = "EMBEDDING";
    public static final String EMBEDDING_STATUS_EMBEDDED = "EMBEDDED";
    public static final String EMBEDDING_STATUS_FAILED = "FAILED";
    public static final String EMBEDDING_STATUS_SKIPPED = "SKIPPED";

    private static final int MAX_BATCH_SIZE = 200;
    private static final Duration DEFAULT_STALE_AFTER = Duration.ofMinutes(15);
    private static final Set<String> INDEXABLE_SOURCE_STATUSES =
            Set.of(DocumentCatalogService.SOURCE_STATUS_READY);
    private static final Set<String> INDEXABLE_UNIT_TYPES = Set.of(
            DocumentCatalogService.SEARCH_UNIT_DOCUMENT,
            DocumentCatalogService.SEARCH_UNIT_PAGE,
            DocumentCatalogService.SEARCH_UNIT_SECTION,
            DocumentCatalogService.SEARCH_UNIT_TABLE,
            DocumentCatalogService.SEARCH_UNIT_CHUNK);

    private static final Logger log = LoggerFactory.getLogger(SearchUnitIndexingService.class);

    private final SearchUnitJpaRepository searchUnits;
    private final SourceFileJpaRepository sourceFiles;
    private final ExtractedArtifactJpaRepository extractedArtifacts;
    private final EmbeddingRecordJpaRepository embeddingRecords;
    private final ObjectMapper objectMapper;
    private final SearchUnitIndexingProperties properties;

    public SearchUnitIndexingService(SearchUnitJpaRepository searchUnits,
                                     SourceFileJpaRepository sourceFiles,
                                     ExtractedArtifactJpaRepository extractedArtifacts,
                                     EmbeddingRecordJpaRepository embeddingRecords,
                                     ObjectMapper objectMapper,
                                     SearchUnitIndexingProperties properties) {
        this.searchUnits = searchUnits;
        this.sourceFiles = sourceFiles;
        this.extractedArtifacts = extractedArtifacts;
        this.embeddingRecords = embeddingRecords;
        this.objectMapper = objectMapper;
        this.properties = properties == null
                ? new SearchUnitIndexingProperties(null, null)
                : properties;
    }

    @Transactional
    public List<ClaimedSearchUnit> claimPending(String workerId,
                                                int batchSize,
                                                Duration staleAfter,
                                                Instant now) {
        return claimPending(workerId, batchSize, staleAfter, now, ClaimScope.unscoped());
    }

    @Transactional
    public List<ClaimedSearchUnit> claimPending(String workerId,
                                                int batchSize,
                                                Duration staleAfter,
                                                Instant now,
                                                ClaimScope scope) {
        int safeBatch = Math.max(1, Math.min(batchSize, MAX_BATCH_SIZE));
        Duration safeStaleAfter = staleAfter == null ? DEFAULT_STALE_AFTER : staleAfter;
        ClaimScope safeScope = scope == null ? ClaimScope.unscoped() : scope;
        if (!safeScope.scoped() && !safeScope.allowUnscopedClaim()) {
            throw new IllegalArgumentException(
                    "SearchUnit indexing claim requires source-scoped filters or allowUnscoped=true");
        }
        if (safeScope.expectedIndexVersion() != null
                && !properties.candidateIndexVersion().equals(safeScope.expectedIndexVersion())) {
            throw new IllegalArgumentException(
                    "expectedIndexVersion must match configured candidate index version: "
                            + properties.candidateIndexVersion());
        }
        List<SearchUnitJpaEntity> candidates = new ArrayList<>();
        if (safeScope.scoped()) {
            candidates.addAll(searchUnits.findIndexingCandidatesScoped(
                    EMBEDDING_STATUS_PENDING,
                    INDEXABLE_SOURCE_STATUSES,
                    safeScope.sourceFileIds().isEmpty(),
                    safeScope.sourceFileIdsOrSentinel(),
                    safeScope.documentVersionIds().isEmpty(),
                    safeScope.documentVersionIdsOrSentinel(),
                    safeScope.parsedArtifactId(),
                    safeScope.searchUnitIds().isEmpty(),
                    safeScope.searchUnitIdsOrSentinel(),
                    safeScope.sourceFileTypes().isEmpty(),
                    safeScope.sourceFileTypesOrSentinel(),
                    safeScope.parserVersions().isEmpty(),
                    safeScope.parserVersionsOrSentinel(),
                    safeBatch * 2));
        } else {
            candidates.addAll(searchUnits.findIndexingCandidates(
                    EMBEDDING_STATUS_PENDING,
                    INDEXABLE_SOURCE_STATUSES,
                    PageRequest.of(0, safeBatch * 2)));
        }

        if (candidates.size() < safeBatch) {
            if (safeScope.scoped()) {
                candidates.addAll(searchUnits.findStaleIndexingClaimsScoped(
                        EMBEDDING_STATUS_EMBEDDING,
                        now.minus(safeStaleAfter),
                        INDEXABLE_SOURCE_STATUSES,
                        safeScope.sourceFileIds().isEmpty(),
                        safeScope.sourceFileIdsOrSentinel(),
                        safeScope.documentVersionIds().isEmpty(),
                        safeScope.documentVersionIdsOrSentinel(),
                        safeScope.parsedArtifactId(),
                        safeScope.searchUnitIds().isEmpty(),
                        safeScope.searchUnitIdsOrSentinel(),
                        safeScope.sourceFileTypes().isEmpty(),
                        safeScope.sourceFileTypesOrSentinel(),
                        safeScope.parserVersions().isEmpty(),
                        safeScope.parserVersionsOrSentinel(),
                        safeBatch - candidates.size()));
            } else {
                candidates.addAll(searchUnits.findStaleIndexingClaims(
                        EMBEDDING_STATUS_EMBEDDING,
                        now.minus(safeStaleAfter),
                        INDEXABLE_SOURCE_STATUSES,
                        PageRequest.of(0, safeBatch - candidates.size())));
            }
        }

        LinkedHashMap<String, SearchUnitJpaEntity> distinct = new LinkedHashMap<>();
        for (SearchUnitJpaEntity candidate : candidates) {
            if (safeScope.scoped() && !safeScope.contains(candidate)) {
                throw new IllegalStateException(
                        "SearchUnit claim escaped requested scope: searchUnitId=" + candidate.getId());
            }
            distinct.putIfAbsent(candidate.getId(), candidate);
        }

        List<SearchUnitJpaEntity> claimed = new ArrayList<>();
        for (SearchUnitJpaEntity unit : distinct.values()) {
            if (claimed.size() >= safeBatch) {
                break;
            }
            if (!EMBEDDING_STATUS_PENDING.equals(unit.getEmbeddingStatus())
                    && !EMBEDDING_STATUS_EMBEDDING.equals(unit.getEmbeddingStatus())) {
                continue;
            }
            Embeddability embeddability = embeddability(unit);
            if (!embeddability.indexable()) {
                unit.markEmbeddingSkipped(embeddability.reason(), now);
                searchUnits.save(unit);
                continue;
            }

            String token = claimToken(workerId, unit.getId());
            unit.claimEmbedding(token, now);
            claimed.add(searchUnits.save(unit));
        }

        Map<String, SourceFileJpaEntity> sourcesById = loadSources(claimed);
        Map<String, ExtractedArtifactJpaEntity> artifactsById = loadArtifacts(claimed);
        return claimed.stream()
                .map(unit -> toClaim(unit, sourcesById.get(unit.getSourceFileId()),
                        artifactsById.get(unit.getExtractedArtifactId())))
                .toList();
    }

    @Transactional
    public CompletionResult markEmbedded(String searchUnitId,
                                         String claimToken,
                                         String contentSha256,
                                         String indexId,
                                         String indexVersion,
                                         String embeddingModel,
                                         String embeddingTextSha256,
                                         String vectorId,
                                         Instant now) {
        Optional<SearchUnitJpaEntity> maybe = searchUnits.findByIdAndEmbeddingClaimToken(searchUnitId, claimToken);
        if (maybe.isEmpty()) {
            return CompletionResult.notApplied("claim token mismatch or SearchUnit not found");
        }
        SearchUnitJpaEntity unit = maybe.get();
        if (!Objects.equals(unit.getContentSha256(), contentSha256)) {
            unit.markEmbeddingPending("stale embedding result: content hash changed while indexing", now);
            searchUnits.save(unit);
            return CompletionResult.stale(unit.getEmbeddingStatusDetail());
        }
        if (!EMBEDDING_STATUS_EMBEDDING.equals(unit.getEmbeddingStatus())) {
            return CompletionResult.notApplied(
                    "SearchUnit is not indexing-eligible for embedded callback: status="
                            + unit.getEmbeddingStatus());
        }

        String stableIndexId = stableIndexId(unit);
        if (indexId != null && !indexId.isBlank() && !stableIndexId.equals(indexId)) {
            return rejectEmbeddedCallback(
                    unit,
                    "indexId mismatch: expected=" + stableIndexId + " actual=" + indexId,
                    now);
        }
        Embeddability embeddability = embeddability(unit);
        if (!embeddability.indexable()) {
            return rejectEmbeddedCallback(unit, "SearchUnit is not indexable: " + embeddability.reason(), now);
        }
        String normalizedIndexVersion = trimToNull(indexVersion);
        String normalizedEmbeddingModel = trimToNull(embeddingModel);
        String normalizedEmbeddingTextSha256 = trimToNull(embeddingTextSha256);
        String normalizedVectorId = trimToNull(vectorId);
        if (normalizedIndexVersion == null) {
            return rejectEmbeddedCallback(unit, "indexVersion is required", now);
        }
        if (normalizedEmbeddingModel == null) {
            return rejectEmbeddedCallback(unit, "embeddingModel is required", now);
        }
        if (normalizedEmbeddingTextSha256 == null) {
            return rejectEmbeddedCallback(unit, "embeddingTextSha256 is required", now);
        }
        if (normalizedVectorId == null) {
            return rejectEmbeddedCallback(unit, "vectorId is required", now);
        }
        if (!properties.candidateIndexVersion().equals(normalizedIndexVersion)) {
            return rejectEmbeddedCallback(
                    unit,
                    "indexVersion mismatch: expected=" + properties.candidateIndexVersion()
                            + " actual=" + normalizedIndexVersion,
                    now);
        }
        if (!properties.embeddingModel().equals(normalizedEmbeddingModel)) {
            return rejectEmbeddedCallback(
                    unit,
                    "embeddingModel mismatch: expected=" + properties.embeddingModel()
                            + " actual=" + normalizedEmbeddingModel,
                    now);
        }
        String expectedEmbeddingTextSha256 = sha256OrNull(firstNonBlank(unit.getEmbeddingText(), unit.getTextContent()));
        if (!Objects.equals(expectedEmbeddingTextSha256, normalizedEmbeddingTextSha256)) {
            return rejectEmbeddedCallback(
                    unit,
                    "embeddingTextSha256 mismatch for search_unit.embedding_text",
                    now);
        }
        String expectedVectorId = versionedVectorId(normalizedIndexVersion, stableIndexId);
        if (!expectedVectorId.equals(normalizedVectorId)) {
            return rejectEmbeddedCallback(
                    unit,
                    "vectorId mismatch: expected=" + expectedVectorId + " actual=" + normalizedVectorId,
                    now);
        }
        unit.markEmbedded(stableIndexId, normalizedIndexVersion, contentSha256, now);
        searchUnits.save(unit);
        upsertEmbeddingRecord(
                unit,
                normalizedIndexVersion,
                normalizedEmbeddingModel,
                normalizedEmbeddingTextSha256,
                normalizedVectorId,
                now);
        return CompletionResult.applied(stableIndexId);
    }

    @Transactional
    public CompletionResult markFailed(String searchUnitId,
                                       String claimToken,
                                       String contentSha256,
                                       String detail,
                                       Instant now) {
        Optional<SearchUnitJpaEntity> maybe = searchUnits.findByIdAndEmbeddingClaimToken(searchUnitId, claimToken);
        if (maybe.isEmpty()) {
            return CompletionResult.notApplied("claim token mismatch or SearchUnit not found");
        }
        SearchUnitJpaEntity unit = maybe.get();
        if (!Objects.equals(unit.getContentSha256(), contentSha256)) {
            unit.markEmbeddingPending("stale failure result: content hash changed while indexing", now);
            searchUnits.save(unit);
            return CompletionResult.stale(unit.getEmbeddingStatusDetail());
        }
        unit.markEmbeddingFailed(limitDetail(detail), now);
        searchUnits.save(unit);
        return CompletionResult.applied(null);
    }

    public static String stableIndexId(SearchUnitJpaEntity unit) {
        return "source_file:" + unit.getSourceFileId()
                + ":unit:" + unit.getCanonicalUnitType()
                + ":" + unit.getUnitKey();
    }

    public static String versionedVectorId(String indexVersion, String stableIndexId) {
        return indexVersion + ":" + stableIndexId;
    }

    private ClaimedSearchUnit toClaim(SearchUnitJpaEntity unit,
                                      SourceFileJpaEntity source,
                                      ExtractedArtifactJpaEntity artifact) {
        String token = unit.getEmbeddingClaimToken();
        String artifactType = artifact == null ? null : artifact.getArtifactType();
        String sourceName = source == null ? null : source.getOriginalFileName();
        return new ClaimedSearchUnit(
                unit.getId(),
                token,
                stableIndexId(unit),
                unit.getSourceFileId(),
                sourceName,
                unit.getExtractedArtifactId(),
                artifactType,
                unit.getCanonicalUnitType(),
                unit.getUnitKey(),
                unit.getTitle(),
                unit.getSectionPath(),
                unit.getPageStart(),
                unit.getPageEnd(),
                firstNonBlank(unit.getEmbeddingText(), unit.getTextContent()),
                unit.getContentSha256(),
                unit.getMetadataJson(),
                indexMetadata(unit, source, artifactType));
    }

    private Map<String, Object> indexMetadata(SearchUnitJpaEntity unit,
                                              SourceFileJpaEntity source,
                                              String artifactType) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        put(metadata, "search_unit_id", unit.getId());
        put(metadata, "source_file_id", unit.getSourceFileId());
        put(metadata, "extracted_artifact_id", unit.getExtractedArtifactId());
        put(metadata, "unit_type", unit.getCanonicalUnitType());
        put(metadata, "unit_key", unit.getUnitKey());
        put(metadata, "page_start", unit.getPageStart());
        put(metadata, "page_end", unit.getPageEnd());
        put(metadata, "section_path", unit.getSectionPath());
        put(metadata, "title", unit.getTitle());
        put(metadata, "content_hash", unit.getContentSha256());
        put(metadata, "content_sha256", unit.getContentSha256());
        put(metadata, "artifact_type", artifactType);
        put(metadata, "index_id", stableIndexId(unit));
        put(metadata, "expected_index_version", properties.candidateIndexVersion());
        put(metadata, "expectedIndexVersion", properties.candidateIndexVersion());
        put(metadata, "candidate_index_version", properties.candidateIndexVersion());
        put(metadata, "candidateIndexVersion", properties.candidateIndexVersion());
        put(metadata, "expected_embedding_model", properties.embeddingModel());
        put(metadata, "expectedEmbeddingModel", properties.embeddingModel());
        put(metadata, "document_id", unit.getDocumentId());
        put(metadata, "documentId", unit.getDocumentId());
        put(metadata, "document_version_id", unit.getDocumentVersionId());
        put(metadata, "documentVersionId", unit.getDocumentVersionId());
        put(metadata, "parsed_artifact_id", unit.getParsedArtifactId());
        put(metadata, "parsedArtifactId", unit.getParsedArtifactId());
        put(metadata, "source_file_type", unit.getSourceFileType());
        put(metadata, "sourceFileType", unit.getSourceFileType());
        put(metadata, "chunk_type", unit.getChunkType());
        put(metadata, "chunkType", unit.getChunkType());
        put(metadata, "location_type", unit.getLocationType());
        put(metadata, "locationType", unit.getLocationType());
        putJsonIfPresent(metadata, "location_json", unit.getLocationJson());
        putJsonIfPresent(metadata, "locationJson", unit.getLocationJson());
        put(metadata, "citation_text", unit.getCitationText());
        put(metadata, "citationText", unit.getCitationText());
        put(metadata, "display_text", unit.getDisplayText());
        put(metadata, "displayText", unit.getDisplayText());
        put(metadata, "debug_text", unit.getDebugText());
        put(metadata, "debugText", unit.getDebugText());
        put(metadata, "parser_name", unit.getParserName());
        put(metadata, "parserName", unit.getParserName());
        put(metadata, "parser_version", unit.getParserVersion());
        put(metadata, "parserVersion", unit.getParserVersion());
        put(metadata, "quality_score", unit.getQualityScore());
        put(metadata, "qualityScore", unit.getQualityScore());
        put(metadata, "confidence_score", unit.getConfidenceScore());
        put(metadata, "confidenceScore", unit.getConfidenceScore());
        JsonNode unitMetadata = parseMetadata(unit.getMetadataJson());
        String unitFileType = textOrNull(unitMetadata, "fileType");
        put(metadata, "fileType", unitFileType == null && source != null ? source.getFileType() : unitFileType);
        put(metadata, "sheetName", textOrNull(unitMetadata, "sheetName"));
        put(metadata, "sheetIndex", intOrNull(unitMetadata, "sheetIndex"));
        put(metadata, "cellRange", firstText(unitMetadata, "cellRange", "range", "usedRange"));
        put(metadata, "range", firstText(unitMetadata, "range", "cellRange", "usedRange"));
        put(metadata, "tableId", firstText(unitMetadata, "tableId", "tableName"));
        put(metadata, "rowStart", intOrNull(unitMetadata, "rowStart"));
        put(metadata, "rowEnd", intOrNull(unitMetadata, "rowEnd"));
        put(metadata, "columnStart", intOrNull(unitMetadata, "columnStart"));
        put(metadata, "columnEnd", intOrNull(unitMetadata, "columnEnd"));
        if (source != null) {
            put(metadata, "source_file_name", source.getOriginalFileName());
            put(metadata, "sourceFileName", source.getOriginalFileName());
            put(metadata, "original_filename", source.getOriginalFileName());
        }
        return metadata;
    }

    private Embeddability embeddability(SearchUnitJpaEntity unit) {
        String type = unit.getCanonicalUnitType();
        String indexableText = firstNonBlank(unit.getEmbeddingText(), unit.getTextContent());
        if (indexableText == null || indexableText.trim().isEmpty()) {
            return Embeddability.skip("embedding_text/text_content is blank; SearchUnit is not embeddable");
        }
        JsonNode unitMetadata = parseMetadata(unit.getMetadataJson());
        if (!INDEXABLE_UNIT_TYPES.contains(type)) {
            return Embeddability.skip("unit_type is not indexable: " + type);
        }
        if (DocumentCatalogService.SEARCH_UNIT_DOCUMENT.equals(type) && !isSpreadsheetMetadata(unitMetadata)) {
            return Embeddability.skip("DOCUMENT SearchUnit is not embedded directly; use PAGE/SECTION/TABLE/CHUNK");
        }
        if (unit.getContentSha256() == null || unit.getContentSha256().isBlank()) {
            return Embeddability.skip("content_sha256 is missing; SearchUnit is not embeddable");
        }
        if (!metadataAllowsIndexing(unitMetadata)) {
            return Embeddability.skip("metadata_json.indexable=false");
        }
        if (requiresV2CitationGate(unit, unitMetadata)) {
            if (unit.getParserVersion() == null || unit.getParserVersion().isBlank()) {
                return Embeddability.skip("parser_version is required for v2 SearchUnit indexing");
            }
            if (unit.getLocationJson() == null || unit.getLocationJson().isBlank()) {
                return Embeddability.skip("location_json is required for v2 SearchUnit indexing");
            }
            if (unit.getCitationText() == null || unit.getCitationText().isBlank()) {
                return Embeddability.skip("citation_text is required for v2 SearchUnit indexing");
            }
            String invalidLocationReason = invalidV2LocationReason(unit, unitMetadata);
            if (invalidLocationReason != null) {
                return Embeddability.skip(invalidLocationReason);
            }
        }
        return Embeddability.yes();
    }

    private void upsertEmbeddingRecord(SearchUnitJpaEntity unit,
                                       String indexVersion,
                                       String embeddingModel,
                                       String embeddingTextSha256,
                                       String vectorId,
                                       Instant now) {
        EmbeddingRecordJpaEntity record = embeddingRecords
                .findBySearchUnitIdAndIndexVersionAndEmbeddingModel(unit.getId(), indexVersion, embeddingModel)
                .orElseGet(() -> new EmbeddingRecordJpaEntity(UUID.randomUUID().toString()));
        record.refresh(
                unit.getId(),
                indexVersion,
                embeddingModel,
                embeddingTextSha256,
                vectorId,
                now);
        embeddingRecords.save(record);
    }

    private String invalidV2LocationReason(SearchUnitJpaEntity unit, JsonNode unitMetadata) {
        JsonNode location = parseMetadata(unit.getLocationJson());
        String locationType = firstNonBlank(
                textOrNull(location, "type"),
                firstNonBlank(unit.getLocationType(), textOrNull(unitMetadata, "fileType")));
        String normalizedType = locationType == null ? "" : locationType.trim().toLowerCase();
        String chunkType = unit.getChunkType() == null ? "" : unit.getChunkType().trim().toLowerCase();
        if ("xlsx".equals(normalizedType) || "spreadsheet".equals(normalizedType)) {
            if (!DocumentCatalogService.XLSX_PIPELINE_VERSION.equals(unit.getParserVersion())) {
                return "xlsx parser_version must be "
                        + DocumentCatalogService.XLSX_PIPELINE_VERSION
                        + " for candidate indexing";
            }
            if (!"exclude_hidden".equals(textOrNull(location, "hidden_policy"))) {
                return "xlsx location_json.hidden_policy=exclude_hidden is required for candidate indexing";
            }
            if (!DocumentCatalogService.XLSX_HIDDEN_POLICY_VERSION.equals(
                    textOrNull(location, "hidden_policy_version"))) {
                return "xlsx location_json.hidden_policy_version="
                        + DocumentCatalogService.XLSX_HIDDEN_POLICY_VERSION
                        + " is required for candidate indexing";
            }
            if (!"workbook_summary".equals(chunkType) && isBlank(textOrNull(location, "sheet_name"))) {
                return "xlsx location_json.sheet_name is required for v2 SearchUnit indexing";
            }
            if (("table".equals(chunkType) || "row_group".equals(chunkType))
                    && isBlank(textOrNull(location, "cell_range"))) {
                return "xlsx location_json.cell_range is required for table/row_group indexing";
            }
        }
        if ("pdf".equals(normalizedType) || "ocr".equals(normalizedType)) {
            boolean hasPage = location.hasNonNull("page_no")
                    || location.hasNonNull("page_label")
                    || location.hasNonNull("physical_page_index");
            if (!hasPage) {
                return "pdf location_json page identifier is required for v2 SearchUnit indexing";
            }
            if ("paragraph".equals(chunkType) && !location.hasNonNull("bbox")) {
                return "pdf paragraph location_json.bbox is required for v2 SearchUnit indexing";
            }
            if (location.path("ocr_used").asBoolean(false) && !location.hasNonNull("ocr_confidence")) {
                return "ocr location_json.ocr_confidence is required for lower-trust indexing";
            }
        }
        return null;
    }

    private boolean requiresV2CitationGate(SearchUnitJpaEntity unit, JsonNode metadata) {
        if (unit.getParserVersion() != null && !unit.getParserVersion().isBlank()) {
            return true;
        }
        if (unit.getLocationJson() != null && !unit.getLocationJson().isBlank()) {
            return true;
        }
        String sourceFileType = unit.getSourceFileType();
        if (sourceFileType != null) {
            String normalized = sourceFileType.trim().toUpperCase();
            if ("SPREADSHEET".equals(normalized) || "PDF".equals(normalized)) {
                return true;
            }
        }
        String fileType = textOrNull(metadata, "fileType");
        if (fileType == null) {
            return false;
        }
        String normalized = fileType.trim().toLowerCase();
        return "xlsx".equals(normalized) || "xlsm".equals(normalized) || "pdf".equals(normalized);
    }

    private boolean metadataAllowsIndexing(JsonNode root) {
        if (root.isMissingNode()) {
            return true;
        }
        JsonNode indexable = root.path("indexable");
        return !indexable.isBoolean() || indexable.asBoolean();
    }

    private static boolean isSpreadsheetMetadata(JsonNode root) {
        String fileType = textOrNull(root, "fileType");
        if (fileType == null) {
            return false;
        }
        String normalized = fileType.trim().toLowerCase();
        return "xlsx".equals(normalized)
                || "xlsm".equals(normalized)
                || "spreadsheet".equals(normalized);
    }

    private JsonNode parseMetadata(String metadataJson) {
        if (metadataJson == null || metadataJson.isBlank()) {
            return objectMapper.getNodeFactory().missingNode();
        }
        try {
            return objectMapper.readTree(metadataJson);
        } catch (IOException | RuntimeException ex) {
            log.warn("SearchUnit metadata_json could not be parsed: {}", ex.toString());
            return objectMapper.getNodeFactory().missingNode();
        }
    }

    private Map<String, SourceFileJpaEntity> loadSources(List<SearchUnitJpaEntity> units) {
        LinkedHashSet<String> ids = new LinkedHashSet<>();
        for (SearchUnitJpaEntity unit : units) {
            ids.add(unit.getSourceFileId());
        }
        if (ids.isEmpty()) {
            return Map.of();
        }
        Map<String, SourceFileJpaEntity> byId = new LinkedHashMap<>();
        for (SourceFileJpaEntity source : sourceFiles.findAllById(ids)) {
            byId.put(source.getId(), source);
        }
        return byId;
    }

    private Map<String, ExtractedArtifactJpaEntity> loadArtifacts(List<SearchUnitJpaEntity> units) {
        LinkedHashSet<String> ids = new LinkedHashSet<>();
        for (SearchUnitJpaEntity unit : units) {
            if (unit.getExtractedArtifactId() != null) {
                ids.add(unit.getExtractedArtifactId());
            }
        }
        if (ids.isEmpty()) {
            return Map.of();
        }
        Map<String, ExtractedArtifactJpaEntity> byId = new LinkedHashMap<>();
        for (ExtractedArtifactJpaEntity artifact : extractedArtifacts.findAllById(ids)) {
            byId.put(artifact.getArtifactId(), artifact);
        }
        return byId;
    }

    private static void put(Map<String, Object> metadata, String key, Object value) {
        if (value != null) {
            metadata.put(key, value);
        }
    }

    private void putJsonIfPresent(Map<String, Object> metadata, String key, String json) {
        if (json == null || json.isBlank()) {
            return;
        }
        JsonNode parsed = parseMetadata(json);
        if (!parsed.isMissingNode() && !parsed.isNull()) {
            metadata.put(key, parsed);
        }
    }

    private static String firstText(JsonNode node, String... fields) {
        for (String field : fields) {
            String value = textOrNull(node, field);
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    private static String textOrNull(JsonNode node, String field) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        JsonNode value = node.path(field);
        return value.isMissingNode() || value.isNull() ? null : value.asText();
    }

    private static String firstNonBlank(String first, String second) {
        return first != null && !first.isBlank() ? first : second;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static Integer intOrNull(JsonNode node, String field) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        JsonNode value = node.path(field);
        if (value.isIntegralNumber()) {
            return value.asInt();
        }
        if (value.isTextual()) {
            try {
                return Integer.parseInt(value.asText().trim());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private static String claimToken(String workerId, String searchUnitId) {
        String normalizedWorker = workerId == null || workerId.isBlank() ? "worker" : workerId.trim();
        return normalizedWorker + ":" + searchUnitId + ":" + UUID.randomUUID();
    }

    private CompletionResult rejectEmbeddedCallback(SearchUnitJpaEntity unit, String detail, Instant now) {
        String limited = limitDetail("embedding callback rejected: " + detail);
        unit.markEmbeddingFailed(limited, now);
        searchUnits.save(unit);
        return CompletionResult.notApplied(limited);
    }

    private static String sha256OrNull(String value) {
        if (value == null) {
            return null;
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                out.append(String.format("%02x", b));
            }
            return out.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String limitDetail(String detail) {
        String normalized = detail == null || detail.isBlank() ? "SearchUnit indexing failed" : detail.trim();
        return normalized.length() <= 2000 ? normalized : normalized.substring(0, 2000);
    }

    public record ClaimScope(
            String sourceFileId,
            List<String> sourceFileIds,
            String documentVersionId,
            List<String> documentVersionIds,
            String parsedArtifactId,
            List<String> searchUnitIds,
            List<String> sourceFileTypes,
            List<String> parserVersions,
            String expectedIndexVersion,
            Boolean allowUnscoped
    ) {
        public ClaimScope {
            sourceFileIds = normalizeIds(sourceFileId, sourceFileIds);
            sourceFileId = sourceFileIds.isEmpty() ? null : sourceFileIds.get(0);
            documentVersionIds = normalizeIds(documentVersionId, documentVersionIds);
            documentVersionId = documentVersionIds.isEmpty() ? null : documentVersionIds.get(0);
            parsedArtifactId = trimToNull(parsedArtifactId);
            searchUnitIds = normalizeIds(searchUnitIds);
            sourceFileTypes = normalizeUpper(sourceFileTypes);
            parserVersions = normalizeIds(parserVersions);
            expectedIndexVersion = trimToNull(expectedIndexVersion);
            allowUnscoped = allowUnscoped != null && allowUnscoped;
        }

        public static ClaimScope unscoped() {
            return new ClaimScope(
                    null,
                    List.of(),
                    null,
                    List.of(),
                    null,
                    List.of(),
                    List.of(),
                    List.of(),
                    null,
                    true);
        }

        boolean scoped() {
            return !sourceFileIds.isEmpty()
                    || !documentVersionIds.isEmpty()
                    || parsedArtifactId != null
                    || !searchUnitIds.isEmpty()
                    || !sourceFileTypes.isEmpty()
                    || !parserVersions.isEmpty();
        }

        boolean allowUnscopedClaim() {
            return Boolean.TRUE.equals(allowUnscoped);
        }

        boolean contains(SearchUnitJpaEntity unit) {
            if (!sourceFileIds.isEmpty() && !sourceFileIds.contains(unit.getSourceFileId())) {
                return false;
            }
            if (!documentVersionIds.isEmpty() && !documentVersionIds.contains(unit.getDocumentVersionId())) {
                return false;
            }
            if (parsedArtifactId != null && !parsedArtifactId.equals(unit.getParsedArtifactId())) {
                return false;
            }
            if (!searchUnitIds.isEmpty() && !searchUnitIds.contains(unit.getId())) {
                return false;
            }
            if (!sourceFileTypes.isEmpty()) {
                String sourceType = unit.getSourceFileType() == null
                        ? null
                        : unit.getSourceFileType().trim().toUpperCase();
                if (!sourceFileTypes.contains(sourceType)) {
                    return false;
                }
            }
            return parserVersions.isEmpty() || parserVersions.contains(unit.getParserVersion());
        }

        List<String> sourceFileIdsOrSentinel() {
            return sourceFileIds.isEmpty() ? List.of("__no_source_file_ids__") : sourceFileIds;
        }

        List<String> documentVersionIdsOrSentinel() {
            return documentVersionIds.isEmpty() ? List.of("__no_document_version_ids__") : documentVersionIds;
        }

        List<String> searchUnitIdsOrSentinel() {
            return searchUnitIds.isEmpty() ? List.of("__no_search_unit_ids__") : searchUnitIds;
        }

        List<String> sourceFileTypesOrSentinel() {
            return sourceFileTypes.isEmpty() ? List.of("__no_source_file_types__") : sourceFileTypes;
        }

        List<String> parserVersionsOrSentinel() {
            return parserVersions.isEmpty() ? List.of("__no_parser_versions__") : parserVersions;
        }

        public ClaimScope(String sourceFileId,
                          String documentVersionId,
                          String parsedArtifactId,
                          List<String> searchUnitIds) {
            this(
                    sourceFileId,
                    List.of(),
                    documentVersionId,
                    List.of(),
                    parsedArtifactId,
                    searchUnitIds,
                    List.of(),
                    List.of(),
                    null,
                    true);
        }

        private static List<String> normalizeIds(String single, List<String> ids) {
            LinkedHashSet<String> normalized = new LinkedHashSet<>();
            String singleValue = trimToNull(single);
            if (singleValue != null) {
                normalized.add(singleValue);
            }
            normalized.addAll(normalizeIds(ids));
            return Collections.unmodifiableList(new ArrayList<>(normalized));
        }

        private static List<String> normalizeIds(List<String> ids) {
            if (ids == null || ids.isEmpty()) {
                return List.of();
            }
            LinkedHashSet<String> normalized = new LinkedHashSet<>();
            for (String id : ids) {
                String value = trimToNull(id);
                if (value != null) {
                    normalized.add(value);
                }
            }
            return Collections.unmodifiableList(new ArrayList<>(normalized));
        }

        private static List<String> normalizeUpper(List<String> ids) {
            if (ids == null || ids.isEmpty()) {
                return List.of();
            }
            LinkedHashSet<String> normalized = new LinkedHashSet<>();
            for (String id : ids) {
                String value = trimToNull(id);
                if (value != null) {
                    normalized.add(value.toUpperCase());
                }
            }
            return Collections.unmodifiableList(new ArrayList<>(normalized));
        }
    }

    private record Embeddability(boolean indexable, String reason) {
        static Embeddability yes() {
            return new Embeddability(true, null);
        }

        static Embeddability skip(String reason) {
            return new Embeddability(false, reason);
        }
    }

    public record ClaimedSearchUnit(
            String searchUnitId,
            String claimToken,
            String indexId,
            String sourceFileId,
            String sourceFileName,
            String extractedArtifactId,
            String artifactType,
            String unitType,
            String unitKey,
            String title,
            String sectionPath,
            Integer pageStart,
            Integer pageEnd,
            String textContent,
            String contentSha256,
            String metadataJson,
            Map<String, Object> indexMetadata
    ) {}

    public record CompletionResult(
            boolean applied,
            boolean stale,
            String indexId,
            String detail
    ) {
        static CompletionResult applied(String indexId) {
            return new CompletionResult(true, false, indexId, null);
        }

        static CompletionResult stale(String detail) {
            return new CompletionResult(false, true, null, detail);
        }

        static CompletionResult notApplied(String detail) {
            return new CompletionResult(false, false, null, detail);
        }
    }
}
