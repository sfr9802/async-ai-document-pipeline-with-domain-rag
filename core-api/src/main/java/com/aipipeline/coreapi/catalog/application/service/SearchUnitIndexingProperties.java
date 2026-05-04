package com.aipipeline.coreapi.catalog.application.service;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "aipipeline.search-unit-indexing")
public record SearchUnitIndexingProperties(
        String candidateIndexVersion,
        String embeddingModel
) {
    public static final String DEFAULT_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-candidate";
    public static final String DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3";

    public SearchUnitIndexingProperties {
        candidateIndexVersion = nonBlankOr(candidateIndexVersion, DEFAULT_CANDIDATE_INDEX_VERSION);
        embeddingModel = nonBlankOr(embeddingModel, DEFAULT_EMBEDDING_MODEL);
    }

    private static String nonBlankOr(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
