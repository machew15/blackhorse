/**
 * Zod validation schemas for all Sentinel API input/output.
 *
 * Every API endpoint validates its input here before touching the database.
 * All API responses are typed against these schemas.
 */

import { z } from "zod";
import { ACCEPTED_MIME_TYPES, MAX_FILE_SIZE_BYTES, MAX_TEXT_LENGTH, MAX_URL_LENGTH } from "@/lib/constants";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

const sourceTypeSchema = z.enum(["pdf", "image", "text", "url", "structured"]);
const statusSchema = z.enum(["verified", "pending", "failed", "unverified"]);

const artifactIdSchema = z
  .string()
  .uuid("Artifact ID must be a valid UUID");

// ---------------------------------------------------------------------------
// Artifact API schemas
// ---------------------------------------------------------------------------

/** Body schema for POST /api/artifacts (file ingestion) */
export const ingestFileSchema = z.object({
  type: z.literal("file"),
  fileName: z.string().min(1).max(255),
  mimeType: z.string().refine(
    (m) => (ACCEPTED_MIME_TYPES as readonly string[]).includes(m),
    { message: "Unsupported MIME type" }
  ),
  sizeBytes: z.number().int().positive().max(MAX_FILE_SIZE_BYTES, {
    message: `File exceeds maximum size of ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB`,
  }),
});

/** Body schema for POST /api/artifacts (URL ingestion) */
export const ingestUrlSchema = z.object({
  type: z.literal("url"),
  url: z
    .string()
    .url("Must be a valid URL")
    .max(MAX_URL_LENGTH, { message: `URL exceeds ${MAX_URL_LENGTH} character limit` }),
});

/** Body schema for POST /api/artifacts (text ingestion) */
export const ingestTextSchema = z.object({
  type: z.literal("text"),
  content: z
    .string()
    .min(1, "Text content cannot be empty")
    .max(MAX_TEXT_LENGTH, { message: `Text exceeds ${MAX_TEXT_LENGTH} character limit` }),
});

export const ingestPayloadSchema = z.discriminatedUnion("type", [
  ingestFileSchema,
  ingestUrlSchema,
  ingestTextSchema,
]);

/** Query params schema for GET /api/artifacts */
export const listArtifactsQuerySchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  pageSize: z.coerce.number().int().positive().max(100).default(20),
  status: statusSchema.optional(),
  sourceType: sourceTypeSchema.optional(),
});

export const artifactIdParamSchema = z.object({
  id: artifactIdSchema,
});

// ---------------------------------------------------------------------------
// Response schemas (for documentation + runtime validation)
// ---------------------------------------------------------------------------

export const artifactResponseSchema = z.object({
  id: z.string().uuid(),
  hashSha256: z.string().length(64),
  hashSha3_512: z.string().length(128),
  timestampIso: z.string().datetime(),
  sourceType: sourceTypeSchema,
  sizeBytes: z.number().nullable(),
  mimeType: z.string().nullable(),
  fileName: z.string().nullable(),
  content: z.string().nullable(),
  sourceUrl: z.string().nullable(),
  metadataJson: z.string(),
  nonce: z.string().length(32),
  status: statusSchema,
  createdAt: z.string().datetime(),
});

export const paginatedArtifactsSchema = z.object({
  items: z.array(artifactResponseSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  pageSize: z.number().int().positive(),
  hasMore: z.boolean(),
});

export type IngestPayload = z.infer<typeof ingestPayloadSchema>;
export type ArtifactResponse = z.infer<typeof artifactResponseSchema>;
export type ListArtifactsQuery = z.infer<typeof listArtifactsQuerySchema>;
