/**
 * Badge — status and type indicators.
 *
 * Design system rule: status badges use a colored dot + text.
 * Never use emoji for verification status.
 */

import { clsx } from "clsx";
import type { VerificationStatus, SourceType, StatusColor } from "@/types";
import { STATUS_COLORS, SOURCE_TYPE_LABELS } from "@/types";

// ---------------------------------------------------------------------------
// Status Badge
// ---------------------------------------------------------------------------

const statusDotClasses: Record<StatusColor, string> = {
  green: "bg-sentinel-green",
  amber: "bg-sentinel-amber",
  red: "bg-sentinel-red",
  gray: "bg-gray-400",
};

const statusTextClasses: Record<StatusColor, string> = {
  green: "text-sentinel-green",
  amber: "text-sentinel-amber",
  red: "text-sentinel-red",
  gray: "text-gray-500",
};

const statusBgClasses: Record<StatusColor, string> = {
  green: "bg-emerald-50 border-emerald-200",
  amber: "bg-amber-50 border-amber-200",
  red: "bg-red-50 border-red-200",
  gray: "bg-gray-50 border-gray-200",
};

const STATUS_LABELS: Record<VerificationStatus, string> = {
  verified: "VERIFIED",
  pending: "PENDING",
  failed: "FAILED",
  unverified: "UNVERIFIED",
};

interface StatusBadgeProps {
  status: VerificationStatus;
  className?: string;
}

/**
 * Verification status badge: colored dot + uppercase text.
 *
 * @example
 * ```tsx
 * <StatusBadge status="verified" />
 * <StatusBadge status="pending" />
 * ```
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const color = STATUS_COLORS[status];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
        "text-xs font-semibold tracking-wide",
        statusBgClasses[color],
        statusTextClasses[color],
        className
      )}
    >
      <span
        className={clsx("h-1.5 w-1.5 rounded-full", statusDotClasses[color])}
        aria-hidden="true"
      />
      {STATUS_LABELS[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Source Type Badge
// ---------------------------------------------------------------------------

const sourceTypeColors: Record<SourceType, string> = {
  pdf: "bg-blue-50 border-blue-200 text-blue-700",
  image: "bg-purple-50 border-purple-200 text-purple-700",
  text: "bg-gray-50 border-gray-200 text-gray-700",
  url: "bg-teal-50 border-teal-200 text-teal-700",
  structured: "bg-orange-50 border-orange-200 text-orange-700",
};

interface SourceTypeBadgeProps {
  sourceType: SourceType;
  className?: string;
}

/**
 * Source type indicator badge.
 */
export function SourceTypeBadge({ sourceType, className }: SourceTypeBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-2 py-0.5",
        "text-xs font-medium uppercase tracking-wider",
        sourceTypeColors[sourceType],
        className
      )}
    >
      {SOURCE_TYPE_LABELS[sourceType]}
    </span>
  );
}
