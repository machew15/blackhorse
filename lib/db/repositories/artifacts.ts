/**
 * Artifact Repository — typed data access layer for the `artifacts` table.
 *
 * All database access for artifacts goes through this module.
 * No raw SQL escapes this file — callers work with typed `ArtifactRecord` objects.
 */

import { eq, desc, and, sql } from "drizzle-orm";
import { db } from "@/lib/db/client";
import { artifacts } from "@/lib/db/schema";
import type { ArtifactRecord, SourceType, VerificationStatus } from "@/types";
import { hashArtifact, generateNonce } from "@/lib/crypto/hash";
import { createTimestamp } from "@/lib/crypto/timestamp";
import { DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE } from "@/lib/constants";
import { randomUUID } from "node:crypto";

// ---------------------------------------------------------------------------
// Types local to this repository
// ---------------------------------------------------------------------------

export interface CreateArtifactInput {
  sourceType: SourceType;
  /** Raw content to hash; required for all source types */
  data: string | Buffer;
  fileName?: string;
  mimeType?: string;
  sizeBytes?: number;
  content?: string;
  sourceUrl?: string;
  metadata?: Record<string, unknown>;
}

export interface ListArtifactsOptions {
  page?: number;
  pageSize?: number;
  status?: VerificationStatus;
  sourceType?: SourceType;
}

// ---------------------------------------------------------------------------
// Core CRUD
// ---------------------------------------------------------------------------

/**
 * Create and persist a new artifact record.
 *
 * The server computes both hashes and the timestamp — no client values are
 * trusted for these fields.
 */
export async function createArtifact(
  input: CreateArtifactInput
): Promise<ArtifactRecord> {
  const { sha256, sha3_512 } = hashArtifact(input.data);
  const nonce = generateNonce();
  const timestampIso = createTimestamp();
  const id = randomUUID();

  const row = {
    id,
    hashSha256: sha256,
    hashSha3_512: sha3_512,
    timestampIso,
    sourceType: input.sourceType,
    sizeBytes: input.sizeBytes ?? null,
    mimeType: input.mimeType ?? null,
    fileName: input.fileName ?? null,
    content: input.content ?? null,
    sourceUrl: input.sourceUrl ?? null,
    metadataJson: JSON.stringify(input.metadata ?? {}),
    nonce,
    status: "unverified" as VerificationStatus,
    createdAt: createTimestamp(),
  };

  await db.insert(artifacts).values(row);
  return row;
}

/**
 * Retrieve a single artifact by ID.
 *
 * @returns The artifact record, or `null` if not found.
 */
export async function getArtifact(id: string): Promise<ArtifactRecord | null> {
  const rows = await db
    .select()
    .from(artifacts)
    .where(eq(artifacts.id, id))
    .limit(1);
  return (rows[0] as ArtifactRecord | undefined) ?? null;
}

/**
 * Retrieve an artifact by its SHA-256 hash.
 * Useful for deduplication checks.
 */
export async function getArtifactByHash(
  hashSha256: string
): Promise<ArtifactRecord | null> {
  const rows = await db
    .select()
    .from(artifacts)
    .where(eq(artifacts.hashSha256, hashSha256))
    .limit(1);
  return (rows[0] as ArtifactRecord | undefined) ?? null;
}

/**
 * List artifacts with optional filtering and pagination.
 */
export async function listArtifacts(options: ListArtifactsOptions = {}): Promise<{
  items: ArtifactRecord[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}> {
  const page = Math.max(1, options.page ?? 1);
  const pageSize = Math.min(
    Math.max(1, options.pageSize ?? DEFAULT_PAGE_SIZE),
    MAX_PAGE_SIZE
  );
  const offset = (page - 1) * pageSize;

  const conditions = [];
  if (options.status) {
    conditions.push(eq(artifacts.status, options.status));
  }
  if (options.sourceType) {
    conditions.push(eq(artifacts.sourceType, options.sourceType));
  }

  const whereClause = conditions.length > 0 ? and(...conditions) : undefined;

  const [rows, countResult] = await Promise.all([
    db
      .select()
      .from(artifacts)
      .where(whereClause)
      .orderBy(desc(artifacts.createdAt))
      .limit(pageSize)
      .offset(offset),
    db
      .select({ count: sql<number>`count(*)` })
      .from(artifacts)
      .where(whereClause),
  ]);

  const total = Number(countResult[0]?.count ?? 0);

  return {
    items: rows as ArtifactRecord[],
    total,
    page,
    pageSize,
    hasMore: offset + rows.length < total,
  };
}

/**
 * Update the verification status of an artifact.
 */
export async function updateArtifactStatus(
  id: string,
  status: VerificationStatus
): Promise<void> {
  await db.update(artifacts).set({ status }).where(eq(artifacts.id, id));
}

/**
 * Hard-delete an artifact record. In production (Stage 4+), prefer soft-delete
 * via status = 'archived' and audit log entries.
 */
export async function deleteArtifact(id: string): Promise<void> {
  await db.delete(artifacts).where(eq(artifacts.id, id));
}

/**
 * Count total ingested artifacts (for dashboard stats).
 */
export async function countArtifacts(): Promise<number> {
  const result = await db
    .select({ count: sql<number>`count(*)` })
    .from(artifacts);
  return Number(result[0]?.count ?? 0);
}
