package com.aipipeline.coreapi.catalog.adapter.out.persistence;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.Set;

public interface SearchUnitJpaRepository extends JpaRepository<SearchUnitJpaEntity, String> {

    boolean existsByExtractedArtifactId(String extractedArtifactId);

    Optional<SearchUnitJpaEntity> findBySourceFileIdAndUnitTypeAndUnitKey(
            String sourceFileId,
            String unitType,
            String unitKey);

    @Query("""
            select unit
            from SearchUnitJpaEntity unit
            where lower(coalesce(unit.textContent, '')) like lower(concat('%', :query, '%'))
               or lower(coalesce(unit.bm25Text, '')) like lower(concat('%', :query, '%'))
               or lower(coalesce(unit.displayText, '')) like lower(concat('%', :query, '%'))
               or lower(coalesce(unit.citationText, '')) like lower(concat('%', :query, '%'))
               or lower(coalesce(unit.debugText, '')) like lower(concat('%', :query, '%'))
            order by
              case
                when lower(coalesce(unit.bm25Text, '')) like lower(concat(:query, '%')) then 0
                when lower(coalesce(unit.displayText, '')) like lower(concat(:query, '%')) then 1
                when lower(coalesce(unit.textContent, '')) like lower(concat(:query, '%')) then 2
                else 3
              end,
              case lower(coalesce(unit.chunkType, unit.unitType, ''))
                when 'row_group' then 0
                when 'paragraph' then 1
                when 'table' then 2
                when 'page' then 3
                when 'sheet_summary' then 4
                when 'document_summary' then 5
                when 'workbook_summary' then 6
                else 7
              end,
              unit.createdAt desc
            """)
    List<SearchUnitJpaEntity> searchByText(@Param("query") String query, Pageable pageable);

    Optional<SearchUnitJpaEntity> findByIdAndEmbeddingClaimToken(String id, String embeddingClaimToken);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
            select unit
            from SearchUnitJpaEntity unit
            where unit.embeddingStatus = :embeddingStatus
              and exists (
                select source.id
                from SourceFileJpaEntity source
                where source.id = unit.sourceFileId
                  and source.status in :sourceStatuses
              )
            order by unit.updatedAt asc
            """)
    List<SearchUnitJpaEntity> findIndexingCandidates(
            @Param("embeddingStatus") String embeddingStatus,
            @Param("sourceStatuses") Set<String> sourceStatuses,
            Pageable pageable);

    @Query(value = """
            select unit.*
            from search_unit unit
            where unit.embedding_status = :embeddingStatus
              and (:sourceFileIdsEmpty = true or unit.source_file_id in (:sourceFileIds))
              and (:documentVersionIdsEmpty = true or unit.document_version_id in (:documentVersionIds))
              and (:parsedArtifactId is null or unit.parsed_artifact_id = :parsedArtifactId)
              and (:searchUnitIdsEmpty = true or unit.id in (:searchUnitIds))
              and (:sourceFileTypesEmpty = true or upper(unit.source_file_type) in (:sourceFileTypes))
              and (:parserVersionsEmpty = true or unit.parser_version in (:parserVersions))
              and unit.embedding_text is not null
              and btrim(unit.embedding_text) <> ''
              and unit.citation_text is not null
              and btrim(unit.citation_text) <> ''
              and unit.location_json is not null
              and exists (
                select 1
                from source_file sf
                where sf.id = unit.source_file_id
                  and sf.status in (:sourceStatuses)
              )
            order by unit.updated_at asc
            limit :limit
            for update skip locked
            """, nativeQuery = true)
    List<SearchUnitJpaEntity> findIndexingCandidatesScoped(
            @Param("embeddingStatus") String embeddingStatus,
            @Param("sourceStatuses") Set<String> sourceStatuses,
            @Param("sourceFileIdsEmpty") boolean sourceFileIdsEmpty,
            @Param("sourceFileIds") List<String> sourceFileIds,
            @Param("documentVersionIdsEmpty") boolean documentVersionIdsEmpty,
            @Param("documentVersionIds") List<String> documentVersionIds,
            @Param("parsedArtifactId") String parsedArtifactId,
            @Param("searchUnitIdsEmpty") boolean searchUnitIdsEmpty,
            @Param("searchUnitIds") List<String> searchUnitIds,
            @Param("sourceFileTypesEmpty") boolean sourceFileTypesEmpty,
            @Param("sourceFileTypes") List<String> sourceFileTypes,
            @Param("parserVersionsEmpty") boolean parserVersionsEmpty,
            @Param("parserVersions") List<String> parserVersions,
            @Param("limit") int limit);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
            select unit
            from SearchUnitJpaEntity unit
            where unit.embeddingStatus = :embeddingStatus
              and unit.embeddingClaimedAt is not null
              and unit.embeddingClaimedAt < :claimedBefore
              and exists (
                select source.id
                from SourceFileJpaEntity source
                where source.id = unit.sourceFileId
                  and source.status in :sourceStatuses
              )
            order by unit.embeddingClaimedAt asc
            """)
    List<SearchUnitJpaEntity> findStaleIndexingClaims(
            @Param("embeddingStatus") String embeddingStatus,
            @Param("claimedBefore") Instant claimedBefore,
            @Param("sourceStatuses") Set<String> sourceStatuses,
            Pageable pageable);

    @Query(value = """
            select unit.*
            from search_unit unit
            where unit.embedding_status = :embeddingStatus
              and unit.embedding_claimed_at is not null
              and unit.embedding_claimed_at < :claimedBefore
              and (:sourceFileIdsEmpty = true or unit.source_file_id in (:sourceFileIds))
              and (:documentVersionIdsEmpty = true or unit.document_version_id in (:documentVersionIds))
              and (:parsedArtifactId is null or unit.parsed_artifact_id = :parsedArtifactId)
              and (:searchUnitIdsEmpty = true or unit.id in (:searchUnitIds))
              and (:sourceFileTypesEmpty = true or upper(unit.source_file_type) in (:sourceFileTypes))
              and (:parserVersionsEmpty = true or unit.parser_version in (:parserVersions))
              and unit.embedding_text is not null
              and btrim(unit.embedding_text) <> ''
              and unit.citation_text is not null
              and btrim(unit.citation_text) <> ''
              and unit.location_json is not null
              and exists (
                select 1
                from source_file sf
                where sf.id = unit.source_file_id
                  and sf.status in (:sourceStatuses)
              )
            order by unit.embedding_claimed_at asc
            limit :limit
            for update skip locked
            """, nativeQuery = true)
    List<SearchUnitJpaEntity> findStaleIndexingClaimsScoped(
            @Param("embeddingStatus") String embeddingStatus,
            @Param("claimedBefore") Instant claimedBefore,
            @Param("sourceStatuses") Set<String> sourceStatuses,
            @Param("sourceFileIdsEmpty") boolean sourceFileIdsEmpty,
            @Param("sourceFileIds") List<String> sourceFileIds,
            @Param("documentVersionIdsEmpty") boolean documentVersionIdsEmpty,
            @Param("documentVersionIds") List<String> documentVersionIds,
            @Param("parsedArtifactId") String parsedArtifactId,
            @Param("searchUnitIdsEmpty") boolean searchUnitIdsEmpty,
            @Param("searchUnitIds") List<String> searchUnitIds,
            @Param("sourceFileTypesEmpty") boolean sourceFileTypesEmpty,
            @Param("sourceFileTypes") List<String> sourceFileTypes,
            @Param("parserVersionsEmpty") boolean parserVersionsEmpty,
            @Param("parserVersions") List<String> parserVersions,
            @Param("limit") int limit);
}
