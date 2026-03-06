/**
 * GET /api/artifacts/:id — Retrieve a single artifact by ID
 */

import { type NextRequest, NextResponse } from "next/server";
import { getArtifact } from "@/lib/db/repositories/artifacts";
import { artifactIdParamSchema } from "@/lib/validation/schemas";
import type { ApiResponse, ArtifactRecord } from "@/types";

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<ApiResponse<ArtifactRecord>>> {
  try {
    const parsed = artifactIdParamSchema.safeParse(params);
    if (!parsed.success) {
      return NextResponse.json(
        { success: false, error: "Invalid artifact ID format" },
        { status: 400 }
      );
    }

    const artifact = await getArtifact(parsed.data.id);
    if (!artifact) {
      return NextResponse.json(
        { success: false, error: "Artifact not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true, data: artifact });
  } catch (err) {
    console.error(`[GET /api/artifacts/${params.id}]`, err);
    return NextResponse.json(
      { success: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}
