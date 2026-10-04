-- ─────────────────────────────────────────────────────────────────────────────
-- StudyBuddy — schema.sql
-- Applied automatically by Postgres on first container start
-- (mounted at /docker-entrypoint-initdb.d/01_schema.sql)
--
-- Run manually on an existing DB:
--   psql $DATABASE_URL -f core/schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- pgvector extension (must be first)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── documents ────────────────────────────────────────────────────────────────
-- One row per ingested file. sha256 is the dedup key.
-- status: queued | processing | ready | failed
CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    filename    TEXT        NOT NULL,
    sha256      TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'queued',
    topic_tags  TEXT[],
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedup: same sha256 → skip re-ingest
CREATE UNIQUE INDEX IF NOT EXISTS ux_documents_sha256
    ON documents (sha256);

-- Fast lookup by filename (re-ingest: same name, new hash)
CREATE INDEX IF NOT EXISTS ix_documents_filename
    ON documents (filename);

-- ── chunks ───────────────────────────────────────────────────────────────────
-- One row per text chunk. Cascades on document delete.
-- embedding is vector(1024) — matches bge-m3 output dim.
-- tsv is a generated tsvector for full-text search.
CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT      NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    page        INT,                 -- 0-indexed page number; NULL for non-PDF
    heading     TEXT,                -- nearest heading above this chunk; NULL if none
    topic       TEXT,                -- TODO: filled by tag_topic activity (Day 2)
    text        TEXT        NOT NULL,
    embedding   VECTOR(1024),        -- bge-m3 embedding; NULL until embed activity completes
    tsv         TSVECTOR    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

-- HNSW index for approximate nearest-neighbour vector search (cosine distance)
-- m=16, ef_construction=64 are safe defaults; tune later if needed.
CREATE INDEX IF NOT EXISTS ix_chunks_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN index for full-text search on tsv
CREATE INDEX IF NOT EXISTS ix_chunks_gin
    ON chunks USING gin (tsv);

-- FK index for fast cascade deletes and doc-level queries
CREATE INDEX IF NOT EXISTS ix_chunks_doc_id
    ON chunks (doc_id);

-- ── answer_cache ─────────────────────────────────────────────────────────────
-- TODO (Day 2): cache LLM answers keyed by question embedding.
-- Table exists now so schema migrations are not needed later.
CREATE TABLE IF NOT EXISTS answer_cache (
    id               BIGSERIAL   PRIMARY KEY,
    q_embedding      VECTOR(1024),
    question         TEXT,
    answer           TEXT,
    source_chunk_ids BIGINT[],
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── questions ─────────────────────────────────────────────────────────────────
-- TODO (Day 2): MCQ and short-answer questions generated from chunks.
CREATE TABLE IF NOT EXISTS questions (
    id         BIGSERIAL PRIMARY KEY,
    chunk_id   BIGINT    REFERENCES chunks (id) ON DELETE CASCADE,
    type       TEXT,       -- 'mcq' | 'short'
    stem       TEXT,
    options    JSONB,      -- for MCQ: {"A": "...", "B": "...", ...}
    answer     TEXT,
    difficulty TEXT,       -- 'easy' | 'medium' | 'hard'
    topic      TEXT
);

-- ── attempts ─────────────────────────────────────────────────────────────────
-- TODO (Day 2): quiz attempt log; feeds TabPFN weak-topic predictor.
CREATE TABLE IF NOT EXISTS attempts (
    id                   BIGSERIAL   PRIMARY KEY,
    question_id          BIGINT      REFERENCES questions (id),
    topic                TEXT,
    correct              BOOLEAN,
    seconds_taken        INT,
    days_since_last_seen INT,
    ts                   TIMESTAMPTZ NOT NULL DEFAULT now()
);
