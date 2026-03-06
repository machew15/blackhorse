/**
 * GET /api/health — System health check
 *
 * Returns protocol version, available stages, and DB liveness.
 * Used by monitoring and the Status dashboard surface.
 */

import { NextResponse } from "next/server";
import { countArtifacts } from "@/lib/db/repositories/artifacts";
import { PROTOCOL_VERSION, PROTOCOL_AVAILABLE_STAGES } from "@/lib/constants";
import { createTimestamp } from "@/lib/crypto/timestamp";

export async function GET() {
  try {
    const artifactCount = await countArtifacts();

    return NextResponse.json({
      success: true,
      data: {
        status: "operational",
        timestamp: createTimestamp(),
        version: "1.0.0",
        stage: 1,
        stageName: "Core Verification Engine",
        database: "connected",
        artifactCount,
        protocol: {
          version: PROTOCOL_VERSION,
          availableStages: PROTOCOL_AVAILABLE_STAGES,
          cryptoReady: false,  // Stage 6 pending
        },
      },
    });
  } catch (err) {
    console.error("[GET /api/health]", err);
    return NextResponse.json(
      {
        success: false,
        data: {
          status: "degraded",
          timestamp: createTimestamp(),
          database: "error",
        },
      },
      { status: 503 }
    );
  }
}
