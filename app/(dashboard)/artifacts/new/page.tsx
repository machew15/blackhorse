/**
 * New Artifact — /artifacts/new
 *
 * The primary ingestion surface for Stage 1.
 * Client-side ingestor component wrapped in a server page with metadata.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ArtifactIngestor } from "@/components/sentinel/ArtifactIngestor";

export const metadata: Metadata = {
  title: "Ingest Artifact",
  description: "Upload a file, paste a URL, or enter text to create a verifiable artifact record.",
};

export default function NewArtifactPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Back navigation */}
      <Link
        href="/artifacts"
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-sentinel-navy transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to artifacts
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-sentinel-navy">
          Ingest Artifact
        </h1>
        <p className="mt-2 text-sm text-gray-500 leading-relaxed">
          Submit an artifact to receive a cryptographic hash pair (SHA-256 +
          SHA-3-512), an immutable ISO 8601 timestamp, and a unique
          verification record. All hashing is performed server-side.
        </p>
      </div>

      {/* Ingestion form */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <ArtifactIngestor />
      </div>

      {/* Info panel */}
      <div className="mt-6 rounded-lg border border-blue-100 bg-blue-50 p-4">
        <h3 className="text-sm font-semibold text-sentinel-navy mb-2">
          What happens when you ingest?
        </h3>
        <ol className="space-y-1.5 text-sm text-gray-600">
          <li className="flex gap-2">
            <span className="font-mono text-xs text-sentinel-accent font-semibold mt-0.5">01</span>
            Your artifact content is received server-side (never hashed client-side)
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-xs text-sentinel-accent font-semibold mt-0.5">02</span>
            SHA-256 and SHA-3-512 digests are computed simultaneously
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-xs text-sentinel-accent font-semibold mt-0.5">03</span>
            An ISO 8601 timestamp and unique nonce are assigned
          </li>
          <li className="flex gap-2">
            <span className="font-mono text-xs text-sentinel-accent font-semibold mt-0.5">04</span>
            The record is persisted and returned as your verification receipt
          </li>
        </ol>
      </div>
    </div>
  );
}
