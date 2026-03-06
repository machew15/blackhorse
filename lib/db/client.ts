/**
 * Blackhorse Sentinel — Database Client
 *
 * Local development: SQLite via better-sqlite3 + Drizzle ORM.
 * Production (Stage 4+): swap to PostgreSQL / Supabase by changing
 * the import and connection string — the repository layer is unaffected.
 *
 * The database file lives at `.data/sentinel.db` (git-ignored).
 * Tables are created on first connection via `initializeSchema()`.
 */

import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import path from "node:path";
import fs from "node:fs";
import * as schema from "./schema";

const DATA_DIR = path.join(process.cwd(), ".data");

/** Ensure the data directory exists before opening the database file. */
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const DB_PATH = path.join(DATA_DIR, "sentinel.db");

const sqlite = new Database(DB_PATH);

// WAL mode enables concurrent reads without blocking writes.
sqlite.pragma("journal_mode = WAL");
// Enforce foreign key constraints (SQLite disables them by default).
sqlite.pragma("foreign_keys = ON");

/** Initialize all schema tables if they do not already exist. */
function initializeSchema(): void {
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS artifacts (
      id             TEXT PRIMARY KEY NOT NULL,
      hash_sha256    TEXT NOT NULL,
      hash_sha3_512  TEXT NOT NULL,
      timestamp_iso  TEXT NOT NULL,
      source_type    TEXT NOT NULL,
      size_bytes     INTEGER,
      mime_type      TEXT,
      file_name      TEXT,
      content        TEXT,
      source_url     TEXT,
      metadata_json  TEXT NOT NULL DEFAULT '{}',
      nonce          TEXT NOT NULL,
      status         TEXT NOT NULL DEFAULT 'unverified',
      created_at     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS verifications (
      id              TEXT PRIMARY KEY NOT NULL,
      artifact_id     TEXT NOT NULL REFERENCES artifacts(id),
      assertion_text  TEXT NOT NULL,
      status          TEXT NOT NULL DEFAULT 'pending',
      evidence_json   TEXT NOT NULL DEFAULT '[]',
      verified_at     TEXT,
      verifier_id     TEXT,
      created_at      TEXT NOT NULL
    );

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
      report_id       TEXT NOT NULL REFERENCES reports(id),
      version_number  TEXT NOT NULL,
      diff_json       TEXT NOT NULL DEFAULT '{}',
      hash            TEXT NOT NULL,
      created_at      TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bhl_records (
      id                   TEXT PRIMARY KEY NOT NULL,
      artifact_id          TEXT NOT NULL REFERENCES artifacts(id),
      bhl_encoded_hash     TEXT,
      protocol_version     TEXT,
      dilithium_signature  TEXT,
      signed_at            TEXT,
      created_at           TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS organizations (
      id            TEXT PRIMARY KEY NOT NULL,
      name          TEXT NOT NULL,
      tier          TEXT NOT NULL DEFAULT 'free',
      settings_json TEXT NOT NULL DEFAULT '{}',
      created_at    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS api_keys (
      id               TEXT PRIMARY KEY NOT NULL,
      org_id           TEXT NOT NULL REFERENCES organizations(id),
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

    CREATE INDEX IF NOT EXISTS idx_artifacts_created_at ON artifacts(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_artifacts_hash_sha256 ON artifacts(hash_sha256);
    CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);
    CREATE INDEX IF NOT EXISTS idx_verifications_artifact_id ON verifications(artifact_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
  `);
}

initializeSchema();

export const db = drizzle(sqlite, { schema });
export { sqlite };
