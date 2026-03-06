/**
 * Artifacts list — /artifacts
 *
 * Server component: fetches artifact list from the API and renders
 * ArtifactCard components. Supports pagination via searchParams.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { ArtifactCard } from "@/components/sentinel/ArtifactCard";
import type { ArtifactRecord, PaginatedResponse } from "@/types";

export const metadata: Metadata = {
  title: "Artifacts",
  description: "Browse and manage all ingested artifacts.",
};

// Revalidate every 30 seconds (ISR)
export const revalidate = 30;

async function fetchArtifacts(
  page = 1
): Promise<PaginatedResponse<ArtifactRecord>> {
  try {
    // Internal API call — runs server-side, no auth header needed at Stage 1
    const baseUrl =
      process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000";
    const res = await fetch(
      `${baseUrl}/api/artifacts?page=${page}&pageSize=20`,
      { cache: "no-store" }
    );
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const json = (await res.json()) as {
      success: boolean;
      data: PaginatedResponse<ArtifactRecord>;
    };
    if (!json.success) throw new Error("API returned error");
    return json.data;
  } catch {
    return { items: [], total: 0, page, pageSize: 20, hasMore: false };
  }
}

interface ArtifactsPageProps {
  searchParams?: { page?: string };
}

export default async function ArtifactsPage({ searchParams }: ArtifactsPageProps) {
  const page = Math.max(1, parseInt(searchParams?.page ?? "1", 10));
  const { items, total, hasMore } = await fetchArtifacts(page);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-sentinel-navy">Artifacts</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {total > 0
              ? `${total.toLocaleString()} artifact${total === 1 ? "" : "s"} ingested`
              : "No artifacts yet"}
          </p>
        </div>
        <Link
          href="/artifacts/new"
          className="inline-flex items-center gap-2 rounded-lg bg-sentinel-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Ingest Artifact
        </Link>
      </div>

      {/* Search — wired at Stage 2 */}
      <div className="mb-6 flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
        <Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
        <input
          type="search"
          placeholder="Search by hash, filename, or ID… (coming soon)"
          className="flex-1 bg-transparent text-sm text-gray-700 placeholder-gray-400 focus:outline-none"
          disabled
        />
      </div>

      {/* List */}
      {items.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="space-y-3">
            {items.map((artifact) => (
              <ArtifactCard key={artifact.id} artifact={artifact} />
            ))}
          </div>

          {/* Pagination */}
          <div className="mt-6 flex items-center justify-between text-sm">
            <span className="text-gray-500">
              Page {page}
            </span>
            <div className="flex gap-2">
              {page > 1 && (
                <Link
                  href={`/artifacts?page=${page - 1}`}
                  className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Previous
                </Link>
              )}
              {hasMore && (
                <Link
                  href={`/artifacts?page=${page + 1}`}
                  className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Next
                </Link>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 bg-white py-16 text-center">
      <div className="mb-4 rounded-full bg-gray-100 p-4">
        <Search className="h-8 w-8 text-gray-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-900">No artifacts yet</h3>
      <p className="mt-1 text-sm text-gray-500 max-w-sm">
        Start by ingesting your first artifact. Every artifact receives a
        cryptographic hash and an immutable timestamp.
      </p>
      <Link
        href="/artifacts/new"
        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-sentinel-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
      >
        <Plus className="h-4 w-4" />
        Ingest your first artifact
      </Link>
    </div>
  );
}
