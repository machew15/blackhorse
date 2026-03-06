/**
 * Blackhorse Sentinel — Timestamp Service
 *
 * All timestamps are:
 *   - Server-assigned (never trust client-provided timestamps)
 *   - ISO 8601 with millisecond precision (e.g. 2026-03-06T18:45:32.891Z)
 *   - Always UTC (the Z suffix is non-negotiable)
 *
 * The design system rule: always display ISO 8601 — never relative time.
 */

/**
 * Generate a server-assigned ISO 8601 timestamp at the current instant.
 *
 * @returns ISO 8601 string with millisecond precision, e.g.
 *          `"2026-03-06T18:45:32.891Z"`
 */
export function createTimestamp(): string {
  return new Date().toISOString();
}

/**
 * Parse and validate an ISO 8601 timestamp string.
 *
 * @throws `Error` if the string is not a valid ISO 8601 date.
 */
export function parseTimestamp(iso: string): Date {
  const date = new Date(iso);
  if (isNaN(date.getTime())) {
    throw new Error(`Invalid ISO 8601 timestamp: "${iso}"`);
  }
  return date;
}

/**
 * Validate that a string is a well-formed ISO 8601 timestamp.
 */
export function isValidTimestamp(iso: string): boolean {
  try {
    parseTimestamp(iso);
    return true;
  } catch {
    return false;
  }
}

/**
 * Format a timestamp for display in the Sentinel UI.
 *
 * Per the design system: always ISO 8601, never relative ("2 hours ago").
 * This function is intentionally a pass-through — the format IS the display.
 */
export function formatTimestamp(iso: string): string {
  return iso;
}

/**
 * Return the number of milliseconds elapsed since a given timestamp.
 * Useful for computing artifact age in audit contexts.
 */
export function msSince(iso: string): number {
  return Date.now() - parseTimestamp(iso).getTime();
}
