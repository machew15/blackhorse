/**
 * Blackhorse Sentinel — Artifact Hashing Utilities
 *
 * All hashing is performed server-side using Node.js native crypto.
 * Never call these functions from client components.
 *
 * Dual-hash strategy:
 *   SHA-256   — industry standard, widely audited
 *   SHA-3-512 — quantum-transition hash; feeds into BHL encoding at Stage 6
 *               when the Blackhorse Protocol crypto stages are available
 *
 * Design note (see ../blackhorse/docs/BHL_SPEC.md):
 *   The SHA-3-512 digest is preserved in `bhl_records.bhl_encoded_hash` at
 *   Stage 6 after BHL encoding + Dilithium signing. Do not change the
 *   hashing function or truncate the digest before that integration.
 */

import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import type { HashResult } from "@/types";
import { NONCE_BYTES, SHA256_HEX_LENGTH, SHA3_512_HEX_LENGTH } from "@/lib/constants";

/**
 * Compute a SHA-256 digest.
 *
 * @param data - Raw bytes or a UTF-8 string.
 * @returns Lowercase hex digest (64 characters).
 */
export function sha256(data: string | Buffer | Uint8Array): string {
  const hash = createHash("sha256").update(data).digest("hex");
  if (hash.length !== SHA256_HEX_LENGTH) {
    throw new Error(`SHA-256 produced unexpected digest length: ${hash.length}`);
  }
  return hash;
}

/**
 * Compute a SHA-3-512 digest.
 *
 * Node.js 16+ with OpenSSL 3.x supports SHA-3 via the built-in `crypto`
 * module. No external library is required.
 *
 * @param data - Raw bytes or a UTF-8 string.
 * @returns Lowercase hex digest (128 characters).
 */
export function sha3_512(data: string | Buffer | Uint8Array): string {
  const hash = createHash("sha3-512").update(data).digest("hex");
  if (hash.length !== SHA3_512_HEX_LENGTH) {
    throw new Error(`SHA-3-512 produced unexpected digest length: ${hash.length}`);
  }
  return hash;
}

/**
 * Generate the canonical dual-hash for an artifact.
 *
 * Both hashes are always computed together. A single-hash record is
 * considered incomplete by the Blackhorse integrity model.
 *
 * @param data - The artifact content (bytes or text).
 * @returns `{ sha256, sha3_512 }` hex digest pair.
 */
export function hashArtifact(data: string | Buffer | Uint8Array): HashResult {
  return {
    sha256: sha256(data),
    sha3_512: sha3_512(data),
  };
}

/**
 * Generate a cryptographically secure nonce.
 *
 * The nonce is appended to the hash record so that two identical artifacts
 * ingested at different times have different database rows and can be
 * independently referenced.
 *
 * @returns 32-character lowercase hex string (16 random bytes).
 */
export function generateNonce(): string {
  return randomBytes(NONCE_BYTES).toString("hex");
}

/**
 * Verify that a given digest matches the re-hash of `data`.
 * Constant-time comparison via `timingSafeEqual` prevents timing attacks.
 *
 * @param data      - Original artifact content.
 * @param expected  - Expected hex digest.
 * @param algorithm - "sha256" or "sha3-512".
 * @returns `true` if the digest matches.
 */
export function verifyHash(
  data: string | Buffer | Uint8Array,
  expected: string,
  algorithm: "sha256" | "sha3-512"
): boolean {
  const actual = createHash(algorithm).update(data).digest("hex");
  if (actual.length !== expected.length) return false;
  // Use timingSafeEqual to prevent timing-based side-channel attacks.
  // Both buffers must be the same length (enforced above).
  return timingSafeEqual(Buffer.from(actual, "hex"), Buffer.from(expected, "hex"));
}

// Re-export for convenience
export type { HashResult };
