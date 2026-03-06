/**
 * Application-wide constants for Blackhorse Sentinel.
 *
 * Named constants prevent magic numbers and make intent explicit.
 * All crypto and hashing constants here mirror the Blackhorse Protocol spec.
 */

// ---------------------------------------------------------------------------
// Protocol integration
// ---------------------------------------------------------------------------

/**
 * The Blackhorse Protocol version this Sentinel build targets.
 * Check ../blackhorse/__init__.py before referencing any Protocol feature.
 * Stage 6+ of Sentinel requires Protocol Stages 3–7 (not yet available).
 */
export const PROTOCOL_VERSION = "0.1.0" as const;

/**
 * Stages of the Blackhorse Protocol that are currently available.
 * Do NOT reference stages > PROTOCOL_AVAILABLE_STAGES in production code.
 */
export const PROTOCOL_AVAILABLE_STAGES = 7 as const;

// ---------------------------------------------------------------------------
// Hashing
// ---------------------------------------------------------------------------

/** SHA-256 produces a 256-bit (64 hex char) digest */
export const SHA256_HEX_LENGTH = 64 as const;

/** SHA-3-512 produces a 512-bit (128 hex char) digest */
export const SHA3_512_HEX_LENGTH = 128 as const;

/** Nonce length in bytes (16 bytes = 128-bit entropy) */
export const NONCE_BYTES = 16 as const;

// ---------------------------------------------------------------------------
// Upload limits (Stage 1)
// ---------------------------------------------------------------------------

/** Maximum file size for artifact ingestion (10 MB) */
export const MAX_FILE_SIZE_BYTES = 10_485_760 as const; // 10 * 1024 * 1024

/** Maximum text artifact length in characters (1 MB of text) */
export const MAX_TEXT_LENGTH = 1_000_000 as const;

/** Maximum URL length in characters */
export const MAX_URL_LENGTH = 2048 as const;

/** Accepted MIME types for file ingestion */
export const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/svg+xml",
  "text/plain",
  "text/csv",
  "text/markdown",
  "application/json",
  "application/xml",
] as const;

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const API_BASE = "/api" as const;

/** Rate limit: max requests per minute for public endpoints */
export const RATE_LIMIT_RPM = 60 as const;

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------

export const DEFAULT_PAGE_SIZE = 20 as const;
export const MAX_PAGE_SIZE = 100 as const;

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------

/** Characters to show on each side of a truncated hash */
export const HASH_TRUNCATE_CHARS = 16 as const;
