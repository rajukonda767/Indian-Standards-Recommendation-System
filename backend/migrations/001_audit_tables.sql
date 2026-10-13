-- =============================================================================
-- Migration 001: Tender Audit Jobs and Items tables
-- Run with: python migrations/run_migration.py 001_audit_tables.sql
-- =============================================================================

-- ─── audit_jobs: one row per audit run ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_jobs (
    id                    UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    status                TEXT        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','running','done','failed')),
    filenames             TEXT[]      NOT NULL DEFAULT '{}',
    doc_type              TEXT,
    total_items           INT         NOT NULL DEFAULT 0,
    done_items            INT         NOT NULL DEFAULT 0,
    -- Scores: NULL means denominator was zero (not "100%")
    coverage              FLOAT,
    currency              FLOAT,
    qco_compliance        FLOAT,
    coverage_denominator  INT         NOT NULL DEFAULT 0,
    currency_denominator  INT         NOT NULL DEFAULT 0,
    qco_denominator       INT         NOT NULL DEFAULT 0,
    status_counts         JSONB       NOT NULL DEFAULT '{}',
    summary               TEXT,
    error_msg             TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS enabled. No policies yet — service-role connection bypasses RLS by default.
-- Policies to be added when user-auth is introduced.
ALTER TABLE audit_jobs ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_audit_jobs_created_at
    ON audit_jobs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_jobs_status
    ON audit_jobs (status);


-- ─── audit_items: one row per line item within a job ─────────────────────────
CREATE TABLE IF NOT EXISTS audit_items (
    id                    UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id                UUID        NOT NULL REFERENCES audit_jobs(id) ON DELETE CASCADE,
    seq_no                INT         NOT NULL,
    item_id               TEXT,           -- item label from tender ("3", "A-07", etc.)
    description           TEXT,
    quantity              TEXT,
    unit                  TEXT,
    status                TEXT,           -- compliant | incomplete | conflict | missing |
                                          -- outdated | superseded | wrong_standard |
                                          -- cannot_verify | not_covered
    badge_color           TEXT,           -- green | yellow | orange | red | grey
    findings              JSONB       NOT NULL DEFAULT '[]',
    cited_standards       JSONB       NOT NULL DEFAULT '[]',
    recommended_standards JSONB       NOT NULL DEFAULT '[]',
    source_tier           TEXT,           -- AUTHORITATIVE | CORROBORATING | CONTEXT_ONLY
    page_refs             INT[]       NOT NULL DEFAULT '{}',
    processing_ms         FLOAT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_audit_items_job_seq UNIQUE (job_id, seq_no)
);

ALTER TABLE audit_items ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_audit_items_job_id
    ON audit_items (job_id);

CREATE INDEX IF NOT EXISTS idx_audit_items_job_seq
    ON audit_items (job_id, seq_no);
