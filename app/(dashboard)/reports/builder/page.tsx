/**
 * Report Builder page — /reports/builder
 *
 * Full-screen composition canvas for Blackhorse Sentinel verification reports.
 * The ReportBuilder is a heavy client component; this server wrapper provides
 * metadata and keeps the layout consistent with the rest of the dashboard.
 */

import type { Metadata } from "next";
import { ReportBuilder } from "@/components/sentinel/ReportBuilder";

export const metadata: Metadata = {
  title: "Report Builder",
  description:
    "Compose, preview, and compile Blackhorse Sentinel verification reports from 17 block types.",
};

export default function ReportBuilderPage() {
  return <ReportBuilder />;
}
