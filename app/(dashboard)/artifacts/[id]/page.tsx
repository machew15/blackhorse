/**
 * Artifact detail — /artifacts/:id
 *
 * Full verification receipt for a single artifact.
 * Shows both hashes, timestamp, nonce, metadata, and status.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { HashDisplay } from "@/components/ui/HashDisplay";
import { StatusBadge, SourceTypeBadge } from "@/components/ui/Badge";
import type { ArtifactRecord } from "@/types";

interface ArtifactDetailPageProps {
  params: { id: string };
}

export async function generateMetadata(
  { params }: ArtifactDetailPageProps
): Promise<Metadata> {
  return {
    title: `Artifact ${params.id.slice(0, 8)}…`,
    description: "View full verification receipt and cryptographic proof.",
  };
}

async function fetchArtifact(id: string): Promise<ArtifactRecord | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/artifacts/${id}`, {
      cache: "no-store",
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const json = (await res.json()) as { success: boolean; data?: ArtifactRecord };
    return json.data ?? null;
  } catch {
    return null;
  }
}

export default async function ArtifactDetailPage({ params }: ArtifactDetailPageProps) {
  const artifact = await fetchArtifact(params.id);
  if (!artifact) notFound();

  const metadata = (() => {
    try {
      return JSON.parse(artifact.metadataJson) as Record<string, unknown>;
    } catch {
      return {};
    }
  })();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Back */}
      <Link
        href="/artifacts"
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-sentinel-navy transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to artifacts
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <SourceTypeBadge sourceType={artifact.sourceType as "pdf" | "image" | "text" | "url" | "structured"} />
            <StatusBadge status={artifact.status as "verified" | "pending" | "failed" | "unverified"} />
          </div>
          <h1 className="text-xl font-bold text-sentinel-navy">
            {artifact.fileName ?? artifact.sourceUrl ?? "Text Artifact"}
          </h1>
          <p className="mt-1 font-mono text-xs text-gray-400">{artifact.id}</p>
        </div>
      </div>

      {/* Verification receipt card */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-100 bg-gray-50 px-6 py-3">
          <h2 className="text-sm font-semibold text-gray-700">Verification Receipt</h2>
        </div>

        <div className="divide-y divide-gray-100">
          {/* Hashes */}
          <div className="px-6 py-5 space-y-4">
            <HashDisplay label="SHA-256" hash={artifact.hashSha256} />
            <HashDisplay label="SHA-3-512" hash={artifact.hashSha3_512} />
          </div>

          {/* Timestamp + Nonce */}
          <div className="grid grid-cols-1 gap-4 px-6 py-5 sm:grid-cols-2">
            <FieldRow label="Timestamp (ISO 8601)" value={artifact.timestampIso} mono />
            <FieldRow label="Nonce" value={artifact.nonce} mono />
          </div>

          {/* Artifact metadata */}
          <div className="grid grid-cols-1 gap-4 px-6 py-5 sm:grid-cols-3">
            {artifact.mimeType && (
              <FieldRow label="MIME Type" value={artifact.mimeType} />
            )}
            {artifact.sizeBytes !== null && (
              <FieldRow
                label="Size"
                value={formatBytes(artifact.sizeBytes)}
              />
            )}
            <FieldRow label="Ingested" value={artifact.createdAt} mono />
          </div>

          {/* Source URL */}
          {artifact.sourceUrl && (
            <div className="px-6 py-5">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Source URL
              </p>
              <a
                href={artifact.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-sentinel-accent hover:underline break-all"
              >
                {artifact.sourceUrl}
                <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
              </a>
            </div>
          )}

          {/* Text content preview */}
          {artifact.content && (
            <div className="px-6 py-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Content Preview
              </p>
              <pre className="max-h-40 overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-xs text-gray-700 whitespace-pre-wrap break-all">
                {artifact.content.slice(0, 2000)}
                {artifact.content.length > 2000 && "\n… (truncated)"}
              </pre>
            </div>
          )}

          {/* Extra metadata */}
          {Object.keys(metadata).length > 0 && (
            <div className="px-6 py-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Metadata
              </p>
              <pre className="rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-xs text-gray-600">
                {JSON.stringify(metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Protocol integration notice */}
      <div className="mt-6 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-gray-600">
        <span className="font-semibold text-sentinel-navy">Stage 6 ready: </span>
        The SHA-3-512 hash above will feed into BHL encoding and Dilithium
        signing when the Blackhorse Protocol crypto stages are integrated.{" "}
        <Link href="/docs" className="text-sentinel-accent hover:underline">
          Learn more →
        </Link>
      </div>
    </div>
  );
}

function FieldRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-0.5">
        {label}
      </p>
      <p
        className={`text-sm text-gray-800 break-all ${mono ? "font-mono" : ""}`}
        style={mono ? { fontVariantNumeric: "tabular-nums" } : undefined}
      >
        {value}
      </p>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
