ALTER TABLE ragmeta.chunks
    DROP CONSTRAINT IF EXISTS chunks_pkey;

ALTER TABLE ragmeta.chunks
    ALTER COLUMN chunk_id TYPE VARCHAR(512),
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (index_version, chunk_id);

CREATE INDEX IF NOT EXISTS idx_ragmeta_chunks_chunk_id
    ON ragmeta.chunks (chunk_id);

ALTER TABLE embedding_record
    ALTER COLUMN vector_id TYPE VARCHAR(1024);
