-- Blackhorse Sentinel — Reference Schema (PostgreSQL-compatible)
-- Generated: 2026-03-06
-- Stage: 1 — Core Verification Engine
--
-- This file is the canonical SQL reference for compliance documentation.
-- Actual migrations are managed by Drizzle ORM (lib/db/schema.ts).
-- For PostgreSQL production deployment (Stage 4+), run this SQL against
-- the Supabase instance and swap the Drizzle dialect from sqlite to pg.

-- ---------------------------------------------------------------------------
-- Core tables (Stage 1)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS artifacts (
    id             TEXT        PRIMARY KEY NOT NULL,
    hash_sha256    TEXT        NOT NULL,
    hash_sha3_512  TEXT        NOT NULL,
    timestamp_iso  TEXT        NOT NULL,
    source_type    TEXT        NOT NULL CHECK (source_type IN ('pdf','image','text','url','structured')),
    size_bytes     INTEGER,
    mime_type      TEXT,
    file_name      TEXT,
    content        TEXT,
    source_url     TEXT,
    metadata_json  TEXT        NOT NULL DEFAULT '{}',
    nonce          TEXT        NOT NULL,
    status         TEXT        NOT NULL DEFAULT 'unverified'
                               CHECK (status IN ('verified','pending','failed','unverified')),
    created_at     TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_created_at  ON artifacts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_hash_sha256 ON artifacts (hash_sha256);
CREATE INDEX IF NOT EXISTS idx_artifacts_status      ON artifacts (status);

CREATE TABLE IF NOT EXISTS verifications (
    id              TEXT PRIMARY KEY NOT NULL,
    artifact_id     TEXT NOT NULL REFERENCES artifacts (id),
    assertion_text  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('verified','pending','failed','unverified')),
    evidence_json   TEXT NOT NULL DEFAULT '[]',
    verified_at     TEXT,
    verifier_id     TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verifications_artifact_id ON verifications (artifact_id);

CREATE TABLE IF NOT EXISTS reports (
    id                   TEXT PRIMARY KEY NOT NULL,
    title                TEXT NOT NULL,
    version              TEXT NOT NULL DEFAULT '1.0.0',
    artifacts_json       TEXT NOT NULL DEFAULT '[]',
    verifications_json   TEXT NOT NULL DEFAULT '[]',
    integrity_hash       TEXT,
    created_at           TEXT NOT NULL,
    exported_at          TEXT
);

CREATE TABLE IF NOT EXISTS report_versions (
    id              TEXT PRIMARY KEY NOT NULL,
    report_id       TEXT NOT NULL REFERENCES reports (id),
    version_number  TEXT NOT NULL,
    diff_json       TEXT NOT NULL DEFAULT '{}',
    hash            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Protocol Integration (Stage 6+)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bhl_records (
    id                   TEXT PRIMARY KEY NOT NULL,
    artifact_id          TEXT NOT NULL REFERENCES artifacts (id),
    bhl_encoded_hash     TEXT,
    protocol_version     TEXT,
    dilithium_signature  TEXT,
    signed_at            TEXT,
    created_at           TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Enterprise (Stage 4+)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organizations (
    id            TEXT PRIMARY KEY NOT NULL,
    name          TEXT NOT NULL,
    tier          TEXT NOT NULL DEFAULT 'free',
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id               TEXT PRIMARY KEY NOT NULL,
    org_id           TEXT NOT NULL REFERENCES organizations (id),
    key_hash         TEXT NOT NULL,
    permissions_json TEXT NOT NULL DEFAULT '[]',
    last_used_at     TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            TEXT PRIMARY KEY NOT NULL,
    org_id        TEXT,
    action        TEXT NOT NULL,
    resource_id   TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    ip            TEXT,
    timestamp     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id    ON audit_logs (org_id);
