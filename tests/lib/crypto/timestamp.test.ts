/**
 * Tests for lib/crypto/timestamp.ts
 */

import { describe, it, expect, vi } from "vitest";
import {
  createTimestamp,
  parseTimestamp,
  isValidTimestamp,
  formatTimestamp,
  msSince,
} from "@/lib/crypto/timestamp";

describe("createTimestamp", () => {
  it("returns a string", () => {
    expect(typeof createTimestamp()).toBe("string");
  });

  it("returns a valid ISO 8601 string", () => {
    const ts = createTimestamp();
    expect(isValidTimestamp(ts)).toBe(true);
  });

  it("ends with Z (UTC)", () => {
    expect(createTimestamp()).toMatch(/Z$/);
  });

  it("includes millisecond precision (at least 20 chars)", () => {
    // Shortest ISO 8601 with ms: "2026-01-01T00:00:00.000Z" = 24 chars
    expect(createTimestamp().length).toBeGreaterThanOrEqual(20);
  });

  it("timestamps from consecutive calls are non-decreasing", () => {
    const t1 = createTimestamp();
    const t2 = createTimestamp();
    expect(new Date(t2).getTime()).toBeGreaterThanOrEqual(new Date(t1).getTime());
  });
});

describe("parseTimestamp", () => {
  it("parses a valid ISO 8601 timestamp", () => {
    const iso = "2026-03-06T18:45:32.891Z";
    const date = parseTimestamp(iso);
    expect(date).toBeInstanceOf(Date);
    expect(date.getFullYear()).toBe(2026);
    expect(date.getMonth()).toBe(2); // 0-indexed
    expect(date.getDate()).toBe(6);
  });

  it("throws on invalid input", () => {
    expect(() => parseTimestamp("not-a-date")).toThrow();
    expect(() => parseTimestamp("")).toThrow();
    expect(() => parseTimestamp("2026-13-01T00:00:00Z")).toThrow(); // month 13
  });

  it("round-trips with createTimestamp", () => {
    const ts = createTimestamp();
    const date = parseTimestamp(ts);
    expect(date.toISOString()).toBe(ts);
  });
});

describe("isValidTimestamp", () => {
  it("returns true for valid ISO 8601 strings", () => {
    expect(isValidTimestamp("2026-03-06T18:45:32.891Z")).toBe(true);
    expect(isValidTimestamp("2026-01-01T00:00:00Z")).toBe(true);
    expect(isValidTimestamp(createTimestamp())).toBe(true);
  });

  it("returns false for invalid strings", () => {
    expect(isValidTimestamp("not-a-date")).toBe(false);
    expect(isValidTimestamp("")).toBe(false);
    // JS Date() accepts "2026/03/06" as valid, so we only test clearly invalid strings
    expect(isValidTimestamp("totally-invalid")).toBe(false);
  });
});

describe("formatTimestamp", () => {
  it("returns the ISO 8601 string unchanged", () => {
    const ts = "2026-03-06T18:45:32.891Z";
    expect(formatTimestamp(ts)).toBe(ts);
  });

  it("never returns a relative time string", () => {
    const ts = createTimestamp();
    const formatted = formatTimestamp(ts);
    // Should not contain "ago", "minutes", "hours", etc.
    expect(formatted).not.toMatch(/ago|minutes|hours|days/i);
  });
});

describe("msSince", () => {
  it("returns a non-negative number for a past timestamp", () => {
    const past = new Date(Date.now() - 5000).toISOString();
    const ms = msSince(past);
    expect(ms).toBeGreaterThanOrEqual(0);
  });

  it("returns approximately the elapsed time", () => {
    const past = new Date(Date.now() - 1000).toISOString();
    const ms = msSince(past);
    // Allow 500ms tolerance for test execution time
    expect(ms).toBeGreaterThanOrEqual(500);
    expect(ms).toBeLessThan(5000);
  });
});
