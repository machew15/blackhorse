/**
 * HashDisplay — renders a cryptographic hash with copy-to-clipboard support.
 *
 * Design system requirements:
 *   - JetBrains Mono font
 *   - Tabular numbers via font-feature-settings
 *   - Truncated by default (first N + … + last N chars)
 *   - Click to expand; copy button always visible
 *   - Never wrap mid-hash without expand context
 */

"use client";

import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import { clsx } from "clsx";
import { HASH_TRUNCATE_CHARS } from "@/lib/constants";

interface HashDisplayProps {
  /** The full hex hash string */
  hash: string;
  /** Optional label shown above the hash (e.g. "SHA-256") */
  label?: string;
  /** Custom CSS class for the container */
  className?: string;
  /** Start expanded. Defaults to false. */
  defaultExpanded?: boolean;
}

/**
 * Renders a cryptographic hash with truncation, expansion, and copy support.
 *
 * @example
 * ```tsx
 * <HashDisplay label="SHA-256" hash={artifact.hashSha256} />
 * <HashDisplay label="SHA-3-512" hash={artifact.hashSha3_512} />
 * ```
 */
export function HashDisplay({
  hash,
  label,
  className,
  defaultExpanded = false,
}: HashDisplayProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const canExpand = hash.length > HASH_TRUNCATE_CHARS * 2 + 3;
  const truncated = canExpand
    ? `${hash.slice(0, HASH_TRUNCATE_CHARS)}…${hash.slice(-8)}`
    : hash;
  const display = expanded ? hash : truncated;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers that block clipboard in non-HTTPS
      const el = document.createElement("textarea");
      el.value = hash;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={clsx("flex flex-col gap-1", className)}>
      {label && (
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          {label}
        </span>
      )}
      <div className="flex items-start gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
        <code
          className={clsx(
            "flex-1 font-mono text-xs text-gray-800 leading-relaxed",
            expanded ? "break-all" : "truncate"
          )}
          style={{ fontVariantNumeric: "tabular-nums" }}
          title={hash}
        >
          {display}
        </code>
        <div className="flex flex-shrink-0 items-center gap-1">
          {canExpand && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="rounded p-1 text-gray-400 hover:text-gray-600 transition-colors"
              title={expanded ? "Collapse hash" : "Expand hash"}
              type="button"
            >
              {expanded ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          )}
          <button
            onClick={handleCopy}
            className="rounded p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="Copy hash to clipboard"
            type="button"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-sentinel-green" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
