/**
 * Shared TypeScript types for Blackhorse Sentinel.
 *
 * All API responses, database records, and component props are typed
 * from this module. The `any` type is never used.
 */

// ---------------------------------------------------------------------------
// Domain enums
// ---------------------------------------------------------------------------

export type SourceType = "pdf" | "image" | "text" | "url" | "structured";

export type VerificationStatus = "verified" | "pending" | "failed" | "unverified";

// ---------------------------------------------------------------------------
// Database record shapes (mirrors lib/db/schema.ts)
// ---------------------------------------------------------------------------

export interface ArtifactRecord {
  id: string;
  hashSha256: string;
  hashSha3_512: string;
  timestampIso: string;
  sourceType: SourceType;
  sizeBytes: number | null;
  mimeType: string | null;
  fileName: string | null;
  /** Stored for text artifacts; null for binary / URL artifacts at Stage 1 */
  content: string | null;
  sourceUrl: string | null;
  metadataJson: string;
  nonce: string;
  status: VerificationStatus;
  createdAt: string;
}

export interface VerificationRecord {
  id: string;
  artifactId: string;
  assertionText: string;
  status: VerificationStatus;
  evidenceJson: string;
  verifiedAt: string | null;
  verifierId: string | null;
  createdAt: string;
}

export interface ReportRecord {
  id: string;
  title: string;
  version: string;
  artifactsJson: string;
  verificationsJson: string;
  integrityHash: string | null;
  createdAt: string;
  exportedAt: string | null;
}

// ---------------------------------------------------------------------------
// Hashing
// ---------------------------------------------------------------------------

export interface HashResult {
  /** Hex-encoded SHA-256 digest (64 chars) */
  sha256: string;
  /** Hex-encoded SHA-3-512 digest (128 chars) */
  sha3_512: string;
}

// ---------------------------------------------------------------------------
// Ingest payloads
// ---------------------------------------------------------------------------

export interface IngestFilePayload {
  type: "file";
  /** The uploaded file (server-side: Buffer; client-side: File) */
  fileName: string;
  mimeType: string;
  sizeBytes: number;
}

export interface IngestUrlPayload {
  type: "url";
  url: string;
}

export interface IngestTextPayload {
  type: "text";
  content: string;
}

export type IngestPayload = IngestFilePayload | IngestUrlPayload | IngestTextPayload;

// ---------------------------------------------------------------------------
// API response shapes
// ---------------------------------------------------------------------------

export type ApiSuccess<T> = { success: true; data: T };
export type ApiError = { success: false; error: string; code?: string };
export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// ---------------------------------------------------------------------------
// UI / component helpers
// ---------------------------------------------------------------------------

export type StatusColor = "green" | "amber" | "red" | "gray";

export const STATUS_COLORS: Record<VerificationStatus, StatusColor> = {
  verified: "green",
  pending: "amber",
  failed: "red",
  unverified: "gray",
} as const;

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  pdf: "PDF",
  image: "Image",
  text: "Text",
  url: "URL",
  structured: "Structured Data",
} as const;
