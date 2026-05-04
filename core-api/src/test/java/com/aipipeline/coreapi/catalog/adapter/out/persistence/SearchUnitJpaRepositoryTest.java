package com.aipipeline.coreapi.catalog.adapter.out.persistence;

import com.aipipeline.coreapi.catalog.application.service.DocumentCatalogService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.persistence.autoconfigure.EntityScan;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.data.domain.PageRequest;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(
        classes = SearchUnitJpaRepositoryTest.JpaTestConfig.class,
        properties = {
        "spring.flyway.enabled=false",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "spring.datasource.url=jdbc:h2:mem:search-unit-repository;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.H2Dialect"
})
@Transactional
class SearchUnitJpaRepositoryTest {

    private static final Instant NOW = Instant.parse("2026-05-05T00:00:00Z");

    @Autowired
    private SearchUnitJpaRepository repository;

    @Autowired
    private SourceFileJpaRepository sourceFiles;

    @Autowired
    private EmbeddingRecordJpaRepository embeddingRecords;

    @SpringBootConfiguration
    @EnableAutoConfiguration
    @EntityScan(basePackageClasses = SearchUnitJpaEntity.class)
    @EnableJpaRepositories(basePackageClasses = SearchUnitJpaRepository.class)
    static class JpaTestConfig {
    }

    @Test
    void search_by_text_and_source_file_types_excludes_matching_non_text_units() {
        SearchUnitJpaEntity textUnit = searchUnit("unit-text", "source-text", "shared keyword text", "TEXT");
        SearchUnitJpaEntity pdfUnit = searchUnit("unit-pdf", "source-pdf", "shared keyword pdf", "PDF");
        SearchUnitJpaEntity failedTextUnit = searchUnit("unit-failed-text", "source-failed-text", "shared keyword failed", "TEXT");
        sourceFiles.saveAll(List.of(
                source("source-text", "notes.txt", "text/plain", "TEXT", DocumentCatalogService.SOURCE_STATUS_READY),
                source("source-pdf", "source.pdf", "application/pdf", "PDF", DocumentCatalogService.SOURCE_STATUS_READY),
                source("source-failed-text", "failed.txt", "text/plain", "TEXT", DocumentCatalogService.SOURCE_STATUS_FAILED)));
        repository.saveAll(List.of(textUnit, pdfUnit, failedTextUnit));

        List<SearchUnitJpaEntity> unfiltered = repository.searchByText("shared", PageRequest.of(0, 10));
        List<SearchUnitJpaEntity> filtered =
                repository.searchByTextAndSourceFileTypes("shared", List.of("TEXT"), PageRequest.of(0, 10));

        assertThat(unfiltered).extracting(SearchUnitJpaEntity::getId)
                .containsExactlyInAnyOrder("unit-text", "unit-pdf");
        assertThat(filtered).extracting(SearchUnitJpaEntity::getId)
                .containsExactly("unit-text");
    }

    @Test
    void search_excludes_stale_text_import_units_even_when_embedding_record_references_them() {
        sourceFiles.save(source(
                "source-text",
                "notes.txt",
                "text/plain",
                "TEXT",
                DocumentCatalogService.SOURCE_STATUS_READY));
        SearchUnitJpaEntity active = searchUnit("unit-active", "source-text", "shared keyword active", "TEXT");
        SearchUnitJpaEntity stale = searchUnit("unit-stale", "source-text", "shared keyword stale", "TEXT");
        stale.markEmbedded("index:unit-stale", "idx-v1", "sha", NOW);
        stale.markEmbeddingSkipped(DocumentCatalogService.STALE_TEXT_IMPORT_UNIT_DETAIL, NOW);
        repository.saveAll(List.of(active, stale));
        EmbeddingRecordJpaEntity embedding = new EmbeddingRecordJpaEntity("embedding-stale");
        embedding.refresh("unit-stale", "idx-v1", "model", "sha", "vector-stale", NOW);
        embeddingRecords.save(embedding);

        List<SearchUnitJpaEntity> filtered =
                repository.searchByTextAndSourceFileTypes("shared", List.of("TEXT"), PageRequest.of(0, 10));

        assertThat(filtered).extracting(SearchUnitJpaEntity::getId)
                .containsExactly("unit-active");
    }

    private static SourceFileJpaEntity source(String sourceFileId,
                                              String fileName,
                                              String mimeType,
                                              String fileType,
                                              String status) {
        return new SourceFileJpaEntity(
                sourceFileId,
                fileName,
                mimeType,
                fileType,
                "local://" + fileName,
                status,
                NOW);
    }

    private static SearchUnitJpaEntity searchUnit(String unitId,
                                                  String sourceFileId,
                                                  String text,
                                                  String sourceFileType) {
        SearchUnitJpaEntity unit = new SearchUnitJpaEntity(
                unitId,
                sourceFileId,
                "artifact-" + unitId,
                DocumentCatalogService.SEARCH_UNIT_CHUNK,
                text,
                "{}",
                DocumentCatalogService.EMBEDDING_STATUS_PENDING,
                NOW);
        unit.applyIngestionV2(
                "doc-" + unitId,
                "docv-" + unitId,
                "pa-" + unitId,
                "source-" + unitId,
                sourceFileType,
                "paragraph",
                sourceFileType.toLowerCase(),
                "{}",
                text,
                text,
                text,
                text,
                "{}",
                "fixture",
                "fixture-v1",
                null,
                null,
                "[]",
                NOW);
        return unit;
    }
}
