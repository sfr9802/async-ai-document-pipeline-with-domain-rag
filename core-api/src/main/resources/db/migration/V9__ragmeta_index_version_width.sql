ALTER TABLE ragmeta.chunks
    ALTER COLUMN index_version TYPE VARCHAR(128);

ALTER TABLE ragmeta.index_builds
    ALTER COLUMN index_version TYPE VARCHAR(128);
