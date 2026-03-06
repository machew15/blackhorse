/**
 * ArtifactIngestor — client-side form for ingesting new artifacts.
 *
 * Three modes (tabs):
 *   File  — drag-and-drop / click-to-upload for PDF, image, or text files
 *   URL   — ingest a URL (hashes the URL string at Stage 1)
 *   Text  — paste or type raw text content
 *
 * On successful ingestion, the result panel shows hashes, timestamp, and
 * the verification status badge.
 */

"use client";

import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { Upload, Link, Type, CheckCircle, AlertCircle } from "lucide-react";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import { HashDisplay } from "@/components/ui/HashDisplay";
import { StatusBadge, SourceTypeBadge } from "@/components/ui/Badge";
import type { ArtifactRecord } from "@/types";
import { ACCEPTED_MIME_TYPES, MAX_FILE_SIZE_BYTES, MAX_TEXT_LENGTH } from "@/lib/constants";

type IngestTab = "file" | "url" | "text";

const TABS: { id: IngestTab; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "file", label: "File", Icon: Upload },
  { id: "url",  label: "URL",  Icon: Link },
  { id: "text", label: "Text", Icon: Type },
];

const ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png,.gif,.webp,.svg,.txt,.csv,.md,.json,.xml";

interface ArtifactIngestorProps {
  /** Called after a successful ingestion with the created artifact record */
  onSuccess?: (artifact: ArtifactRecord) => void;
}

/**
 * Full artifact ingestion form with File / URL / Text tabs.
 *
 * All hashing and timestamping is performed server-side. The form only
 * sends raw content — never client-computed hashes.
 */
export function ArtifactIngestor({ onSuccess }: ArtifactIngestorProps) {
  const [activeTab, setActiveTab] = useState<IngestTab>("file");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ArtifactRecord | null>(null);

  const [urlInput, setUrlInput] = useState("");
  const [textInput, setTextInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setError(null);
    setResult(null);
  };

  // ---- File ingestion ----

  const handleFile = async (file: File) => {
    reset();
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError(`File exceeds maximum size of ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB.`);
      return;
    }
    if (!(ACCEPTED_MIME_TYPES as readonly string[]).includes(file.type)) {
      setError(`Unsupported file type: ${file.type}.`);
      return;
    }
    await ingestFile(file);
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) await handleFile(file);
  };

  const handleFileInput = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await handleFile(file);
  };

  const ingestFile = async (file: File) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/artifacts", {
        method: "POST",
        body: formData,
      });
      const json = (await res.json()) as { success: boolean; data?: ArtifactRecord; error?: string };

      if (!json.success || !json.data) {
        setError(json.error ?? "Ingestion failed");
        return;
      }
      setResult(json.data);
      onSuccess?.(json.data);
    } catch {
      setError("Network error — please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ---- URL ingestion ----

  const ingestUrl = async () => {
    reset();
    if (!urlInput.trim()) { setError("Please enter a URL."); return; }
    setLoading(true);
    try {
      const res = await fetch("/api/artifacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "url", url: urlInput.trim() }),
      });
      const json = (await res.json()) as { success: boolean; data?: ArtifactRecord; error?: string };
      if (!json.success || !json.data) { setError(json.error ?? "Ingestion failed"); return; }
      setResult(json.data);
      onSuccess?.(json.data);
    } catch {
      setError("Network error — please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ---- Text ingestion ----

  const ingestText = async () => {
    reset();
    if (!textInput.trim()) { setError("Please enter some text."); return; }
    if (textInput.length > MAX_TEXT_LENGTH) {
      setError(`Text exceeds the ${MAX_TEXT_LENGTH.toLocaleString()} character limit.`);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/artifacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "text", content: textInput }),
      });
      const json = (await res.json()) as { success: boolean; data?: ArtifactRecord; error?: string };
      if (!json.success || !json.data) { setError(json.error ?? "Ingestion failed"); return; }
      setResult(json.data);
      onSuccess?.(json.data);
    } catch {
      setError("Network error — please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full">
      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => { setActiveTab(id); reset(); }}
            className={clsx(
              "flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
              activeTab === id
                ? "bg-white text-sentinel-navy shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="mt-4">
        {/* ---- File tab ---- */}
        {activeTab === "file" && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={clsx(
              "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors",
              dragging
                ? "border-sentinel-accent bg-blue-50"
                : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100"
            )}
          >
            <Upload className={clsx("mb-3 h-10 w-10", dragging ? "text-sentinel-accent" : "text-gray-400")} />
            <p className="text-sm font-medium text-gray-700">
              {dragging ? "Drop to ingest" : "Drag and drop a file, or click to browse"}
            </p>
            <p className="mt-1 text-xs text-gray-400">
              PDF, images, text files — up to {MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="hidden"
              onChange={handleFileInput}
            />
          </div>
        )}

        {/* ---- URL tab ---- */}
        {activeTab === "url" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                URL to ingest
              </label>
              <p className="mt-0.5 text-xs text-gray-500">
                At Stage 1, the URL string itself is hashed. Full content fetching arrives at Stage 2.
              </p>
            </div>
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://example.com/document.pdf"
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder-gray-400 focus:border-sentinel-accent focus:outline-none focus:ring-1 focus:ring-sentinel-accent"
            />
            <Button onClick={ingestUrl} loading={loading} disabled={!urlInput.trim()}>
              Ingest URL
            </Button>
          </div>
        )}

        {/* ---- Text tab ---- */}
        {activeTab === "text" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Text content
              </label>
              <p className="mt-0.5 text-xs text-gray-500">
                Paste or type the content to hash and timestamp.
              </p>
            </div>
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              rows={6}
              placeholder="Enter text content to ingest..."
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm placeholder-gray-400 focus:border-sentinel-accent focus:outline-none focus:ring-1 focus:ring-sentinel-accent"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">
                {textInput.length.toLocaleString()} / {MAX_TEXT_LENGTH.toLocaleString()} chars
              </span>
              <Button onClick={ingestText} loading={loading} disabled={!textInput.trim()}>
                Ingest Text
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="mt-4 animate-slide-up rounded-xl border border-sentinel-green/30 bg-emerald-50 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-sentinel-green" />
            <span className="font-semibold text-sentinel-green">Artifact ingested successfully</span>
            <div className="ml-auto flex items-center gap-2">
              <SourceTypeBadge sourceType={result.sourceType as "pdf" | "image" | "text" | "url" | "structured"} />
              <StatusBadge status={result.status as "unverified"} />
            </div>
          </div>

          <div className="grid gap-3">
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Artifact ID
              </p>
              <code className="block rounded bg-white px-3 py-1.5 font-mono text-xs text-gray-800 border border-gray-200">
                {result.id}
              </code>
            </div>
            <HashDisplay label="SHA-256" hash={result.hashSha256} />
            <HashDisplay label="SHA-3-512" hash={result.hashSha3_512} />
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Timestamp (ISO 8601)
              </p>
              <code className="block rounded bg-white px-3 py-1.5 font-mono text-xs text-gray-800 border border-gray-200">
                {result.timestampIso}
              </code>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => { setResult(null); setUrlInput(""); setTextInput(""); }}
          >
            Ingest another artifact
          </Button>
        </div>
      )}
    </div>
  );
}
