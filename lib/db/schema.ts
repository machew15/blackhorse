/**
 * Drizzle ORM schema — Blackhorse Sentinel
 *
 * SQLite dialect for local development. All column names and types
 * are PostgreSQL-compatible so the migration to Supabase at Stage 4
 * requires only a dialect swap.
 *
 * See schema.sql for the raw SQL version and for reference in
 * compliance documentation.
 */

import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

// ---------------------------------------------------------------------------
// artifacts
// ---------------------------------------------------------------------------

export const artifacts = sqliteTable("artifacts", {
  id: text("id").primaryKey().notNull(),

  /** SHA-256 hex digest of artifact content */
  hashSha256: text("hash_sha256").notNull(),

  /** SHA-3-512 hex digest — quantum-transition hash, feeds BHL at Stage 6 */
  hashSha3_512: text("hash_sha3_512").notNull(),

  /** Server-assigned ISO 8601 timestamp with ms precision */
  timestampIso: text("timestamp_iso").notNull(),

  /** 'pdf' | 'image' | 'text' | 'url' | 'structured' */
  sourceType: text("source_type").notNull(),

  /** File size in bytes; null for text/URL artifacts */
  sizeBytes: integer("size_bytes"),

  /** MIME type reported by the upload; null for text/URL */
  mimeType: text("mime_type"),

  /** Original file name for file uploads; null otherwise */
  fileName: text("file_name"),

  /** Full content for text artifacts; null for binary/URL (stored in R2 at Stage 4+) */
  content: text("content"),

  /** Source URL for URL artifacts; null otherwise */
  sourceUrl: text("source_url"),

  /** JSON object: additional metadata (tags, description, etc.) */
  metadataJson: text("metadata_json").notNull().default("{}"),

  /** Server-generated 32-char hex nonce; prevents duplicate hash records */
  nonce: text("nonce").notNull(),

  /** 'verified' | 'pending' | 'failed' | 'unverified' */
  status: text("status").notNull().default("unverified"),

  createdAt: text("created_at").notNull(),
});

// ---------------------------------------------------------------------------
// verifications
// ---------------------------------------------------------------------------

export const verifications = sqliteTable("verifications", {
  id: text("id").primaryKey().notNull(),
  artifactId: text("artifact_id")
    .notNull()
    .references(() => artifacts.id),
  assertionText: text("assertion_text").notNull(),
  status: text("status").notNull().default("pending"),
  evidenceJson: text("evidence_json").notNull().default("[]"),
  verifiedAt: text("verified_at"),
  verifierId: text("verifier_id"),
  createdAt: text("created_at").notNull(),
});

// ---------------------------------------------------------------------------
// reports
// ---------------------------------------------------------------------------

export const reports = sqliteTable("reports", {
  id: text("id").primaryKey().notNull(),
  title: text("title").notNull(),
  version: text("version").notNull().default("1.0.0"),
  artifactsJson: text("artifacts_json").notNull().default("[]"),
  verificationsJson: text("verifications_json").notNull().default("[]"),
  integrityHash: text("integrity_hash"),
  createdAt: text("created_at").notNull(),
  exportedAt: text("exported_at"),
});

export const reportVersions = sqliteTable("report_versions", {
  id: text("id").primaryKey().notNull(),
  reportId: text("report_id")
    .notNull()
    .references(() => reports.id),
  versionNumber: text("version_number").notNull(),
  diffJson: text("diff_json").notNull().default("{}"),
  hash: text("hash").notNull(),
  createdAt: text("created_at").notNull(),
});

// ---------------------------------------------------------------------------
// Protocol integration (Stage 6+) — table exists now; rows added at Stage 6
// ---------------------------------------------------------------------------

export const bhlRecords = sqliteTable("bhl_records", {
  id: text("id").primaryKey().notNull(),
  artifactId: text("artifact_id")
    .notNull()
    .references(() => artifacts.id),
  /** BHL-encoded SHA-3-512 hash of the artifact */
  bhlEncodedHash: text("bhl_encoded_hash"),
  /** Blackhorse Protocol version used for encoding */
  protocolVersion: text("protocol_version"),
  /** Dilithium signature — populated at Stage 6 */
  dilithiumSignature: text("dilithium_signature"),
  signedAt: text("signed_at"),
  createdAt: text("created_at").notNull(),
});

// ---------------------------------------------------------------------------
// Enterprise (Stage 4+) — schema present; populated at Stage 4
// ---------------------------------------------------------------------------

export const organizations = sqliteTable("organizations", {
  id: text("id").primaryKey().notNull(),
  name: text("name").notNull(),
  tier: text("tier").notNull().default("free"),
  settingsJson: text("settings_json").notNull().default("{}"),
  createdAt: text("created_at").notNull(),
});

export const apiKeys = sqliteTable("api_keys", {
  id: text("id").primaryKey().notNull(),
  orgId: text("org_id")
    .notNull()
    .references(() => organizations.id),
  keyHash: text("key_hash").notNull(),
  permissionsJson: text("permissions_json").notNull().default("[]"),
  lastUsedAt: text("last_used_at"),
  createdAt: text("created_at").notNull(),
});

export const auditLogs = sqliteTable("audit_logs", {
  id: text("id").primaryKey().notNull(),
  orgId: text("org_id"),
  action: text("action").notNull(),
  resourceId: text("resource_id"),
  metadataJson: text("metadata_json").notNull().default("{}"),
  ip: text("ip"),
  timestamp: text("timestamp").notNull(),
});
