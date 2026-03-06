/**
 * Tests for lib/crypto/hash.ts
 *
 * Verifies SHA-256, SHA-3-512, dual-hash, nonce generation,
 * and hash verification utilities.
 */

import { describe, it, expect } from "vitest";
import {
  sha256,
  sha3_512,
  hashArtifact,
  generateNonce,
  verifyHash,
} from "@/lib/crypto/hash";
import { SHA256_HEX_LENGTH, SHA3_512_HEX_LENGTH, NONCE_BYTES } from "@/lib/constants";

describe("sha256", () => {
  it("produces a 64-character hex digest", () => {
    expect(sha256("hello")).toHaveLength(SHA256_HEX_LENGTH);
  });

  it("output is all lowercase hex characters", () => {
    expect(sha256("abc")).toMatch(/^[0-9a-f]+$/);
  });

  it("is deterministic — same input always gives same output", () => {
    const input = "sovereign data";
    expect(sha256(input)).toBe(sha256(input));
  });

  it("is sensitive to input changes (avalanche effect)", () => {
    expect(sha256("hello")).not.toBe(sha256("hello!"));
  });

  it("accepts Buffer input", () => {
    const buf = Buffer.from("test data");
    const str = sha256("test data");
    expect(sha256(buf)).toBe(str);
  });

  it("handles empty string input", () => {
    // SHA-256("") = e3b0c44298fc1c149afb...
    const result = sha256("");
    expect(result).toHaveLength(SHA256_HEX_LENGTH);
    expect(result).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  });
});

describe("sha3_512", () => {
  it("produces a 128-character hex digest", () => {
    expect(sha3_512("hello")).toHaveLength(SHA3_512_HEX_LENGTH);
  });

  it("is deterministic", () => {
    const input = "blackhorse sentinel";
    expect(sha3_512(input)).toBe(sha3_512(input));
  });

  it("differs from SHA-256 output", () => {
    expect(sha3_512("hello")).not.toBe(sha256("hello"));
  });

  it("is sensitive to input changes", () => {
    expect(sha3_512("hello")).not.toBe(sha3_512("Hello"));
  });

  it("handles empty string input", () => {
    const result = sha3_512("");
    expect(result).toHaveLength(SHA3_512_HEX_LENGTH);
  });

  it("accepts Buffer input", () => {
    const buf = Buffer.from("quantum test");
    const str = sha3_512("quantum test");
    expect(sha3_512(buf)).toBe(str);
  });
});

describe("hashArtifact", () => {
  it("returns both sha256 and sha3_512 fields", () => {
    const result = hashArtifact("test content");
    expect(result).toHaveProperty("sha256");
    expect(result).toHaveProperty("sha3_512");
  });

  it("sha256 is 64 hex chars", () => {
    expect(hashArtifact("data").sha256).toHaveLength(SHA256_HEX_LENGTH);
  });

  it("sha3_512 is 128 hex chars", () => {
    expect(hashArtifact("data").sha3_512).toHaveLength(SHA3_512_HEX_LENGTH);
  });

  it("is deterministic for the same input", () => {
    const a = hashArtifact("determinism test");
    const b = hashArtifact("determinism test");
    expect(a.sha256).toBe(b.sha256);
    expect(a.sha3_512).toBe(b.sha3_512);
  });

  it("produces different digests for different inputs", () => {
    const a = hashArtifact("content A");
    const b = hashArtifact("content B");
    expect(a.sha256).not.toBe(b.sha256);
    expect(a.sha3_512).not.toBe(b.sha3_512);
  });

  it("sha256 and sha3_512 always differ from each other", () => {
    const { sha256: h256, sha3_512: h3 } = hashArtifact("same input");
    // Different algorithms produce different outputs (with overwhelming probability)
    expect(h256).not.toBe(h3);
  });
});

describe("generateNonce", () => {
  it(`produces a ${NONCE_BYTES * 2}-character hex string`, () => {
    expect(generateNonce()).toHaveLength(NONCE_BYTES * 2);
  });

  it("produces a valid hex string", () => {
    expect(generateNonce()).toMatch(/^[0-9a-f]+$/);
  });

  it("generates unique nonces on each call", () => {
    const nonces = new Set(Array.from({ length: 100 }, generateNonce));
    expect(nonces.size).toBe(100);
  });
});

describe("verifyHash", () => {
  it("returns true for a matching SHA-256 digest", () => {
    const data = "verify me";
    const hash = sha256(data);
    expect(verifyHash(data, hash, "sha256")).toBe(true);
  });

  it("returns false for a non-matching digest", () => {
    expect(verifyHash("real data", sha256("other data"), "sha256")).toBe(false);
  });

  it("returns true for a matching SHA-3-512 digest", () => {
    const data = "quantum verify";
    const hash = sha3_512(data);
    expect(verifyHash(data, hash, "sha3-512")).toBe(true);
  });

  it("returns false for mismatched length", () => {
    expect(verifyHash("data", "abc", "sha256")).toBe(false);
  });
});
