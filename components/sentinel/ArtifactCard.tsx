/**
 * ArtifactCard — compact artifact summary for the artifacts list view.
 *
 * Displays: source type badge, truncated SHA-256, ISO 8601 timestamp,
 * status badge, and a link to the full artifact detail page.
 */

import Link from "next/link";
import { ArrowUpRight, FileText, Globe, Image, Database } from "lucide-react";
import { StatusBadge, SourceTypeBadge } from "@/components/ui/Badge";
import type { ArtifactRecord, SourceType } from "@/types";
import { HASH_TRUNCATE_CHARS } from "@/lib/constants";

interface ArtifactCardProps {
  artifact: ArtifactRecord;
}

const sourceTypeIcons: Record<SourceType, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  image: Image,
  text: FileText,
  url: Globe,
  structured: Database,
};

function truncateHash(hash: string): string {
  return `${hash.slice(0, HASH_TRUNCATE_CHARS)}…${hash.slice(-8)}`;
}

/**
 * Compact card for the artifact list view.
 *
 * @example
 * ```tsx
 * {artifacts.map(a => <ArtifactCard key={a.id} artifact={a} />)}
 * ```
 */
export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const Icon = sourceTypeIcons[artifact.sourceType as SourceType] ?? FileText;

  return (
    <Link
      href={`/artifacts/${artifact.id}`}
      className="group block rounded-lg border border-gray-200 bg-white p-4 transition-all hover:border-sentinel-accent hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: icon + metadata */}
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex-shrink-0 rounded-md bg-gray-100 p-2">
            <Icon className="h-4 w-4 text-gray-500" />
          </div>
          <div className="min-w-0 flex-1">
            {/* Filename or source identifier */}
            <p className="truncate text-sm font-medium text-gray-900">
              {artifact.fileName ?? artifact.sourceUrl ?? `Text artifact`}
            </p>
            {/* SHA-256 truncated */}
            <p className="mt-0.5 font-mono text-xs text-gray-500" style={{ fontVariantNumeric: "tabular-nums" }}>
              {truncateHash(artifact.hashSha256)}
            </p>
            {/* Timestamp — always ISO 8601, never relative */}
            <p className="mt-0.5 text-xs text-gray-400">{artifact.timestampIso}</p>
          </div>
        </div>

        {/* Right: badges + link arrow */}
        <div className="flex flex-shrink-0 flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <SourceTypeBadge sourceType={artifact.sourceType as SourceType} />
            <StatusBadge status={artifact.status as "verified" | "pending" | "failed" | "unverified"} />
          </div>
          {artifact.sizeBytes !== null && (
            <span className="text-xs text-gray-400">
              {formatBytes(artifact.sizeBytes)}
            </span>
          )}
        </div>
      </div>

      {/* Arrow icon visible on hover */}
      <div className="mt-3 flex items-center justify-end opacity-0 transition-opacity group-hover:opacity-100">
        <span className="flex items-center gap-1 text-xs font-medium text-sentinel-accent">
          View artifact <ArrowUpRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </Link>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
