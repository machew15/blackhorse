/**
 * POST /api/artifacts  — Ingest a new artifact
 * GET  /api/artifacts  — List artifacts with pagination
 *
 * Auth: TODO Stage 4 — add Clerk middleware before write endpoints.
 * Rate: TODO Stage 4 — add rate limiting middleware.
 */

import { type NextRequest, NextResponse } from "next/server";
import { createArtifact, listArtifacts } from "@/lib/db/repositories/artifacts";
import { ingestPayloadSchema, listArtifactsQuerySchema } from "@/lib/validation/schemas";
import type { ApiResponse } from "@/types";
import { MAX_FILE_SIZE_BYTES, ACCEPTED_MIME_TYPES } from "@/lib/constants";

// ---------------------------------------------------------------------------
// POST — ingest a new artifact
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const contentType = request.headers.get("content-type") ?? "";

    // ---- multipart/form-data (file upload) ----
    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData();
      const file = formData.get("file") as File | null;

      if (!file) {
        return errorResponse("No file provided in form data", 400);
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        return errorResponse(
          `File exceeds maximum size of ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB`,
          413
        );
      }
      if (!(ACCEPTED_MIME_TYPES as readonly string[]).includes(file.type)) {
        return errorResponse(`Unsupported file type: ${file.type}`, 415);
      }

      const buffer = Buffer.from(await file.arrayBuffer());
      const sourceType = file.type.startsWith("image/")
        ? "image"
        : file.type === "application/pdf"
        ? "pdf"
        : "text";

      const artifact = await createArtifact({
        sourceType,
        data: buffer,
        fileName: file.name,
        mimeType: file.type,
        sizeBytes: file.size,
      });

      return successResponse(artifact, 201);
    }

    // ---- application/json (text or URL) ----
    if (contentType.includes("application/json")) {
      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return errorResponse("Invalid JSON body", 400);
      }

      const parsed = ingestPayloadSchema.safeParse(body);
      if (!parsed.success) {
        return errorResponse(parsed.error.issues[0]?.message ?? "Validation error", 422);
      }

      const payload = parsed.data;

      if (payload.type === "text") {
        const artifact = await createArtifact({
          sourceType: "text",
          data: payload.content,
          content: payload.content,
          sizeBytes: Buffer.byteLength(payload.content, "utf8"),
          mimeType: "text/plain",
        });
        return successResponse(artifact, 201);
      }

      if (payload.type === "url") {
        const artifact = await createArtifact({
          sourceType: "url",
          data: payload.url,          // hash the URL string itself at Stage 1
          sourceUrl: payload.url,
          sizeBytes: Buffer.byteLength(payload.url, "utf8"),
          mimeType: "text/uri-list",
        });
        return successResponse(artifact, 201);
      }

      return errorResponse("Unsupported ingest type", 400);
    }

    return errorResponse(
      "Unsupported Content-Type. Use multipart/form-data for files or application/json for text/URLs.",
      415
    );
  } catch (err) {
    console.error("[POST /api/artifacts]", err);
    return errorResponse("Internal server error", 500);
  }
}

// ---------------------------------------------------------------------------
// GET — list artifacts
// ---------------------------------------------------------------------------

export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url);
    const rawQuery = Object.fromEntries(searchParams.entries());

    const parsed = listArtifactsQuerySchema.safeParse(rawQuery);
    if (!parsed.success) {
      return errorResponse(parsed.error.issues[0]?.message ?? "Invalid query params", 400);
    }

    const result = await listArtifacts(parsed.data);
    return successResponse(result);
  } catch (err) {
    console.error("[GET /api/artifacts]", err);
    return errorResponse("Internal server error", 500);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function successResponse<T>(data: T, status = 200): NextResponse<ApiResponse<T>> {
  return NextResponse.json({ success: true, data }, { status });
}

function errorResponse(error: string, status: number): NextResponse {
  return NextResponse.json({ success: false, error }, { status });
}
