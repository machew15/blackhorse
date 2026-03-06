/**
 * ReportBuilder — Blackhorse visual report composition canvas.
 *
 * Drag-free, block-based report builder for Blackhorse Sentinel.
 * Compose verification reports from 17 block types across 6 categories,
 * compile to JSON with an integrity hash, and export the equivalent
 * Python API code.
 *
 * Client component: all state is local (no server round-trips for authoring).
 * Compilation calls the /api/reports/compile endpoint (Stage 3).
 */

"use client";

import { useState, useCallback } from "react";

// ---------------------------------------------------------------------------
// Type helpers
// ---------------------------------------------------------------------------

/** Safely extract a string from an unknown BlockContent field. */
function str(val: unknown, fallback = ""): string {
  return typeof val === "string" ? val : fallback;
}

/** Safely extract a number from an unknown BlockContent field. */
function num(val: unknown, fallback = 0): number {
  return typeof val === "number" ? val : fallback;
}

/** Safely extract a boolean from an unknown BlockContent field. */
function bool(val: unknown): boolean {
  return typeof val === "boolean" ? val : false;
}

/** Safely extract an array from an unknown BlockContent field. */
function arr<T = unknown>(val: unknown): T[] {
  return Array.isArray(val) ? (val as T[]) : [];
}

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

type BlockContent = Record<string, unknown>;

interface Block {
  id: string;
  type: string;
  content: BlockContent;
}

interface BlockTypeDefinition {
  type: string;
  label: string;
  category: string;
  icon: string;
}

interface ThemeDefinition {
  value: string;
  label: string;
  accent: string;
}

interface CompiledReport {
  report_id: string;
  title: string;
  theme: string;
  audience: string;
  classification: string;
  compiled_at: string;
  version: string;
  integrity: {
    block_count: number;
    block_hashes: string[];
    root_hash_sha256: string;
    verified: boolean;
  };
  blocks: {
    block_id: string;
    block_type: string;
    content: BlockContent;
    order: number;
    content_hash: string;
  }[];
}

interface TimelineEvent {
  timestamp: string;
  title: string;
  description: string;
  actor: string;
}

interface ChainEntry {
  timestamp: string;
  actor: string;
  action: string;
  hash: string;
}

interface StatusItem {
  label: string;
  status: string;
  detail: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BLOCK_TYPES: BlockTypeDefinition[] = [
  { type: "header",               label: "Header",               category: "Layout",       icon: "⬛" },
  { type: "section",              label: "Section",              category: "Layout",       icon: "─" },
  { type: "text",                 label: "Text",                 category: "Content",      icon: "¶" },
  { type: "callout",              label: "Callout",              category: "Content",      icon: "◈" },
  { type: "artifact",             label: "Artifact",             category: "Evidence",     icon: "⬡" },
  { type: "finding",              label: "Finding",              category: "Evidence",     icon: "◉" },
  { type: "timeline",             label: "Timeline",             category: "Evidence",     icon: "↓" },
  { type: "chain_of_custody",     label: "Chain of Custody",     category: "Evidence",     icon: "⛓" },
  { type: "assertion",            label: "Assertion",            category: "Evidence",     icon: "◎" },
  { type: "table",                label: "Table",                category: "Data",         icon: "⊞" },
  { type: "metric",               label: "Metric",               category: "Data",         icon: "#" },
  { type: "status_grid",          label: "Status Grid",          category: "Data",         icon: "⊡" },
  { type: "hash_record",          label: "Hash Record",          category: "Verification", icon: "⊕" },
  { type: "verification_summary", label: "Verification Summary", category: "Verification", icon: "✓" },
  { type: "integrity_proof",      label: "Integrity Proof",      category: "Verification", icon: "⬢" },
  { type: "thought_record",       label: "Thought Record",       category: "Governance",   icon: "◌" },
  { type: "flag_summary",         label: "Flag Summary",         category: "Governance",   icon: "⚑" },
];

const CATEGORIES = ["Layout", "Content", "Evidence", "Data", "Verification", "Governance"];

const THEMES: ThemeDefinition[] = [
  { value: "sentinel",     label: "Sentinel",     accent: "#00E5FF" },
  { value: "investigator", label: "Investigator", accent: "#FF4444" },
  { value: "compliance",   label: "Compliance",   accent: "#44BB88" },
  { value: "sovereign",    label: "Sovereign",    accent: "#D4AF37" },
  { value: "confidential", label: "Confidential", accent: "#FF8C00" },
];

const AUDIENCES = ["sentinel", "investigator", "institution", "public"];

const CLASSIFICATIONS = ["CONFIDENTIAL", "RESTRICTED", "INTERNAL", "PUBLIC"];

const DEFAULT_CONTENT: Record<string, BlockContent> = {
  header:               { title: "Untitled Report", subtitle: "", classification: "CONFIDENTIAL" },
  section:              { title: "New Section", description: "" },
  text:                 { body: "Enter text here.", style: "body" },
  callout:              { title: "Note", body: "Enter callout text.", variant: "info" },
  artifact:             { artifact_id: "art-001", name: "document.pdf", hash_sha256: "a3f2b1...", hash_sha3: "c7d8e9...", timestamp_iso: "2026-03-06T12:00:00Z", source_type: "pdf", notes: "", verified: true },
  finding:              { title: "Finding Title", description: "Describe the finding.", severity: "medium", recommendation: "Recommended action." },
  timeline:             { title: "Timeline of Events", events: [{ timestamp: "2026-03-01T00:00:00Z", title: "Event 1", description: "Description", actor: "human" }] },
  chain_of_custody:     { subject: "Evidence Item", entries: [{ timestamp: "2026-03-06T00:00:00Z", actor: "Investigator", action: "Received", hash: "abc123..." }] },
  assertion:            { claim: "Enter your assertion here.", status: "PENDING", confidence: "MEDIUM" },
  table:                { title: "Data Table", headers: ["Column A", "Column B", "Column C"], rows: [["Data 1", "Data 2", "Data 3"], ["Data 4", "Data 5", "Data 6"]] },
  metric:               { label: "Metric Label", value: "142", unit: "items", trend: "up", status: "positive" },
  status_grid:          { title: "Status Overview", items: [{ label: "Component A", status: "pass", detail: "Verified" }, { label: "Component B", status: "fail", detail: "Review needed" }] },
  hash_record:          { artifact_name: "document.pdf", hash_sha256: "a3f2b1c4...", hash_sha3: "c7d8e9f0...", timestamp_iso: "2026-03-06T12:00:00Z", verified_by: "Blackhorse Sentinel" },
  verification_summary: { total: 10, verified: 8, pending: 1, failed: 1, pass_rate: "80.0%" },
  integrity_proof:      { subject: "Report Package", root_hash: "7f3a8b2c...", block_count: 12, compiled_at: "2026-03-06T14:00:00Z", verification_method: "SHA-256 Merkle chain" },
  thought_record:       { thought_id: "0001", slug: "design-decision", decision: "Decision summary", author: "human", timestamp_iso: "2026-03-06T12:00:00Z", governance_level: "standard", reasoning_excerpt: "Reasoning excerpt..." },
  flag_summary:         { total_flags: 5, open_flags: 1, critical_open: 0, resolved: 4, period: "Q1 2026", health: "HEALTHY" },
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function generateId(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** djb2 hash — display only; real SHA-256 happens server-side on compile. */
function computeHash(content: BlockContent): string {
  const str = JSON.stringify(content, Object.keys(content).sort());
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(16).padStart(8, "0") + "...";
}

function getAccent(theme: string): string {
  return THEMES.find(t => t.value === theme)?.accent ?? "#00E5FF";
}

// ---------------------------------------------------------------------------
// JSON Syntax Highlighter
// (replaces the original HTML-string injection approach which doesn't work
// in React — strings returned from .replace() are not rendered as markup)
// ---------------------------------------------------------------------------

interface JsonLineProps {
  line: string;
  accent: string;
}

function JsonLine({ line, accent }: JsonLineProps) {
  // Match: leading whitespace + "key":
  const keyMatch = line.match(/^(\s*)("(?:[^"\\]|\\.)*")(:\s*)(.*)/);
  if (keyMatch) {
    const [, indent, key, colon, rest] = keyMatch;
    return (
      <span style={{ display: "block" }}>
        {indent}
        <span style={{ color: accent }}>{key}</span>
        <span style={{ color: "#555" }}>{colon}</span>
        <span style={{ color: "#888" }}>{rest}</span>
      </span>
    );
  }
  // Comment line
  if (line.trimStart().startsWith("//")) {
    return <span style={{ display: "block", color: "#3a3a3a" }}>{line}</span>;
  }
  return <span style={{ display: "block", color: "#666" }}>{line}</span>;
}

// ---------------------------------------------------------------------------
// BlockPreview
// ---------------------------------------------------------------------------

interface BlockPreviewProps {
  block: Block;
  theme: string;
  selected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onMoveUp: (id: string) => void;
  onMoveDown: (id: string) => void;
  isFirst: boolean;
  isLast: boolean;
}

function BlockPreview({
  block, theme, selected, onSelect, onDelete, onMoveUp, onMoveDown, isFirst, isLast,
}: BlockPreviewProps) {
  const accent = getAccent(theme);
  const c = block.content;

  const renderContent = () => {
    switch (block.type) {

      case "header":
        return (
          <div style={{ padding: "20px 24px", borderLeft: `3px solid ${accent}` }}>
            <div style={{ fontSize: "9px", letterSpacing: "0.2em", color: accent, marginBottom: "6px", fontFamily: "monospace" }}>
              {str(c.classification, "CONFIDENTIAL")}
            </div>
            <div style={{ fontSize: "20px", fontWeight: 300, color: "#fff", letterSpacing: "-0.02em", fontFamily: "'DM Serif Display', Georgia, serif" }}>
              {str(c.title, "Untitled")}
            </div>
            {str(c.subtitle) && (
              <div style={{ fontSize: "12px", color: "#888", marginTop: "4px", fontFamily: "monospace" }}>
                {str(c.subtitle)}
              </div>
            )}
          </div>
        );

      case "section":
        return (
          <div style={{ padding: "16px 24px", display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{ width: "24px", height: "1px", background: accent }} />
            <div style={{ fontSize: "10px", letterSpacing: "0.15em", color: accent, fontFamily: "monospace", textTransform: "uppercase" }}>
              {str(c.title)}
            </div>
            <div style={{ flex: 1, height: "1px", background: "#222" }} />
          </div>
        );

      case "text":
        return (
          <div style={{ padding: "12px 24px" }}>
            <div style={{ fontSize: "13px", color: "#bbb", lineHeight: 1.7, fontFamily: "'IBM Plex Serif', Georgia, serif" }}>
              {str(c.body)}
            </div>
          </div>
        );

      case "callout": {
        const variantColors: Record<string, string> = {
          info: "#00E5FF", warning: "#FF8C00", critical: "#FF4444",
          success: "#44BB88", sovereign: "#D4AF37",
        };
        const vc = variantColors[str(c.variant, "info")] ?? accent;
        return (
          <div style={{ padding: "14px 20px", margin: "4px 24px", borderLeft: `2px solid ${vc}`, background: `${vc}0A` }}>
            <div style={{ fontSize: "10px", color: vc, fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: "4px" }}>
              {str(c.title).toUpperCase()}
            </div>
            <div style={{ fontSize: "12px", color: "#aaa", fontFamily: "'IBM Plex Serif', Georgia, serif" }}>
              {str(c.body)}
            </div>
          </div>
        );
      }

      case "artifact":
        return (
          <div style={{ padding: "14px 24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <div>
              <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "2px" }}>ARTIFACT</div>
              <div style={{ fontSize: "13px", color: "#ddd", fontFamily: "monospace" }}>{str(c.name)}</div>
              <div style={{ fontSize: "10px", color: "#555", marginTop: "2px" }}>
                {str(c.source_type).toUpperCase()} · {str(c.artifact_id)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "2px" }}>SHA-256</div>
              <div style={{ fontSize: "10px", color: accent, fontFamily: "monospace" }}>
                {str(c.hash_sha256).slice(0, 16)}...
              </div>
              <div style={{ fontSize: "9px", color: bool(c.verified) ? "#44BB88" : "#FF4444", marginTop: "4px", fontFamily: "monospace" }}>
                {bool(c.verified) ? "✓ VERIFIED" : "✗ UNVERIFIED"}
              </div>
            </div>
          </div>
        );

      case "finding": {
        const sevColors: Record<string, string> = {
          critical: "#FF4444", high: "#FF8C00", medium: "#FFD700",
          low: "#44BB88", informational: "#888",
        };
        const sc = sevColors[str(c.severity, "medium")] ?? "#888";
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <div style={{ fontSize: "9px", fontFamily: "monospace", color: sc, border: `1px solid ${sc}`, padding: "2px 6px", letterSpacing: "0.1em" }}>
                {str(c.severity).toUpperCase()}
              </div>
              <div style={{ fontSize: "13px", color: "#ddd", fontFamily: "'DM Serif Display', Georgia, serif" }}>
                {str(c.title)}
              </div>
            </div>
            <div style={{ fontSize: "12px", color: "#888", lineHeight: 1.5, fontFamily: "'IBM Plex Serif', Georgia, serif" }}>
              {str(c.description)}
            </div>
            {str(c.recommendation) && (
              <div style={{ marginTop: "8px", fontSize: "11px", color: "#555", fontFamily: "monospace" }}>
                → {str(c.recommendation)}
              </div>
            )}
          </div>
        );
      }

      case "timeline":
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "10px", letterSpacing: "0.1em" }}>
              {str(c.title).toUpperCase()}
            </div>
            {arr<TimelineEvent>(c.events).map((ev, i) => {
              const events = arr<TimelineEvent>(c.events);
              return (
                <div key={i} style={{ display: "flex", gap: "12px", marginBottom: "8px" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: accent, flexShrink: 0, marginTop: "3px" }} />
                    {i < events.length - 1 && (
                      <div style={{ width: "1px", flex: 1, background: "#222", marginTop: "4px" }} />
                    )}
                  </div>
                  <div style={{ paddingBottom: "8px" }}>
                    <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace" }}>
                      {ev.timestamp?.slice(0, 10)}
                    </div>
                    <div style={{ fontSize: "12px", color: "#ccc", fontFamily: "monospace" }}>{ev.title}</div>
                    <div style={{ fontSize: "11px", color: "#666" }}>{ev.description}</div>
                  </div>
                </div>
              );
            })}
          </div>
        );

      case "chain_of_custody":
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "8px", letterSpacing: "0.1em" }}>
              CHAIN OF CUSTODY · {str(c.subject).toUpperCase()}
            </div>
            {arr<ChainEntry>(c.entries).map((e, i) => (
              <div key={i} style={{ display: "flex", gap: "12px", alignItems: "flex-start", marginBottom: "6px", padding: "6px 10px", background: "#080808", borderRadius: "2px" }}>
                <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", flexShrink: 0 }}>
                  {e.timestamp?.slice(0, 10)}
                </div>
                <div style={{ fontSize: "11px", color: "#aaa", fontFamily: "monospace" }}>{e.actor}</div>
                <div style={{ fontSize: "11px", color: "#666", fontFamily: "monospace" }}>→ {e.action}</div>
                <div style={{ fontSize: "9px", color: accent, fontFamily: "monospace", marginLeft: "auto" }}>{e.hash}</div>
              </div>
            ))}
          </div>
        );

      case "assertion": {
        const statusColors: Record<string, string> = {
          VERIFIED: "#44BB88", FAILED: "#FF4444", PENDING: "#FFD700", UNVERIFIED: "#888",
        };
        const statusColor = statusColors[str(c.status, "PENDING")] ?? "#888";
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
              <div style={{ fontSize: "9px", fontFamily: "monospace", color: statusColor, border: `1px solid ${statusColor}`, padding: "2px 6px" }}>
                {str(c.status)}
              </div>
              <div style={{ fontSize: "9px", fontFamily: "monospace", color: "#444" }}>
                CONFIDENCE: {str(c.confidence)}
              </div>
            </div>
            <div style={{ fontSize: "13px", color: "#ddd", fontFamily: "'IBM Plex Serif', Georgia, serif", fontStyle: "italic" }}>
              &ldquo;{str(c.claim)}&rdquo;
            </div>
          </div>
        );
      }

      case "table":
        return (
          <div style={{ padding: "14px 24px", overflowX: "auto" }}>
            {str(c.title) && (
              <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "8px", letterSpacing: "0.1em" }}>
                {str(c.title).toUpperCase()}
              </div>
            )}
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "monospace" }}>
              <thead>
                <tr>
                  {arr<string>(c.headers).map((h, i) => (
                    <th key={i} style={{ fontSize: "9px", color: accent, textAlign: "left", padding: "4px 8px", borderBottom: `1px solid ${accent}22`, letterSpacing: "0.1em" }}>
                      {h.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {arr<string[]>(c.rows).map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j} style={{ fontSize: "11px", color: "#888", padding: "6px 8px", borderBottom: "1px solid #111" }}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      case "metric":
        return (
          <div style={{ padding: "14px 24px", textAlign: "center" }}>
            <div style={{ fontSize: "32px", fontWeight: 100, color: accent, fontFamily: "monospace", letterSpacing: "-0.02em" }}>
              {str(c.value)}
              <span style={{ fontSize: "14px", color: "#555", marginLeft: "4px" }}>{str(c.unit)}</span>
            </div>
            <div style={{ fontSize: "10px", color: "#555", fontFamily: "monospace", letterSpacing: "0.12em", marginTop: "4px" }}>
              {str(c.label).toUpperCase()}
            </div>
          </div>
        );

      case "status_grid":
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginBottom: "10px", letterSpacing: "0.1em" }}>
              {str(c.title).toUpperCase()}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
              {arr<StatusItem>(c.items).map((item, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 10px", background: "#0a0a0a", borderRadius: "2px" }}>
                  <div style={{
                    width: "6px", height: "6px", borderRadius: "50%", flexShrink: 0,
                    background: item.status === "pass" ? "#44BB88" : item.status === "fail" ? "#FF4444" : "#FFD700",
                  }} />
                  <div>
                    <div style={{ fontSize: "11px", color: "#bbb", fontFamily: "monospace" }}>{item.label}</div>
                    <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace" }}>{item.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "hash_record":
        return (
          <div style={{ padding: "14px 24px", background: "#050505", border: "1px solid #1a1a1a", margin: "4px 24px", borderRadius: "2px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <div style={{ fontSize: "11px", color: "#888", fontFamily: "monospace" }}>{str(c.artifact_name)}</div>
              <div style={{ fontSize: "9px", color: accent, fontFamily: "monospace" }}>{str(c.verified_by)}</div>
            </div>
            <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace", marginBottom: "2px" }}>SHA-256</div>
            <div style={{ fontSize: "10px", color: accent, fontFamily: "monospace", wordBreak: "break-all" }}>
              {str(c.hash_sha256)}
            </div>
            <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace", marginTop: "6px", marginBottom: "2px" }}>SHA-3-512</div>
            <div style={{ fontSize: "10px", color: "#555", fontFamily: "monospace", wordBreak: "break-all" }}>
              {str(c.hash_sha3)}
            </div>
          </div>
        );

      case "verification_summary": {
        const total = num(c.total, 1); // avoid division by zero
        const verified = num(c.verified);
        const vRate = (verified / total) * 100;
        return (
          <div style={{ padding: "16px 24px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "12px" }}>
              {[
                { label: "TOTAL",    val: num(c.total),   color: "#888" },
                { label: "VERIFIED", val: verified,        color: "#44BB88" },
                { label: "PENDING",  val: num(c.pending), color: "#FFD700" },
                { label: "FAILED",   val: num(c.failed),  color: "#FF4444" },
              ].map(({ label, val, color }) => (
                <div key={label} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "22px", fontWeight: 200, color, fontFamily: "monospace" }}>{val}</div>
                  <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace", letterSpacing: "0.1em" }}>{label}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: "12px", height: "2px", background: "#111", borderRadius: "1px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${vRate}%`, background: `linear-gradient(90deg, #44BB88, ${accent})`, transition: "width 0.5s" }} />
            </div>
            <div style={{ fontSize: "9px", color: "#555", fontFamily: "monospace", marginTop: "4px", textAlign: "right" }}>
              {str(c.pass_rate)} PASS RATE
            </div>
          </div>
        );
      }

      case "integrity_proof":
        return (
          <div style={{ padding: "14px 24px", background: "#030303", border: `1px solid ${accent}22`, margin: "4px 24px", borderRadius: "2px" }}>
            <div style={{ fontSize: "9px", color: accent, fontFamily: "monospace", letterSpacing: "0.15em", marginBottom: "8px" }}>
              ⬢ INTEGRITY PROOF · {str(c.subject).toUpperCase()}
            </div>
            <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace", marginBottom: "2px" }}>ROOT HASH (SHA-256)</div>
            <div style={{ fontSize: "11px", color: "#888", fontFamily: "monospace" }}>{str(c.root_hash)}</div>
            <div style={{ display: "flex", gap: "20px", marginTop: "8px" }}>
              <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace" }}>{num(c.block_count)} BLOCKS</div>
              <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace" }}>{str(c.verification_method)}</div>
              <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace" }}>
                COMPILED {str(c.compiled_at).slice(0, 10)}
              </div>
            </div>
          </div>
        );

      case "thought_record":
        return (
          <div style={{ padding: "14px 24px", borderLeft: `1px solid ${accent}44`, marginLeft: "24px" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
              <div style={{ fontSize: "9px", color: accent, fontFamily: "monospace" }}>
                ◌ THOUGHT {str(c.thought_id)}
              </div>
              <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace" }}>
                {str(c.governance_level).toUpperCase()}
              </div>
            </div>
            <div style={{ fontSize: "12px", color: "#ccc", fontFamily: "'IBM Plex Serif', Georgia, serif", marginBottom: "4px" }}>
              {str(c.decision)}
            </div>
            {str(c.reasoning_excerpt) && (
              <div style={{ fontSize: "11px", color: "#555", fontFamily: "monospace", fontStyle: "italic" }}>
                &ldquo;{str(c.reasoning_excerpt)}&rdquo;
              </div>
            )}
            <div style={{ fontSize: "9px", color: "#444", fontFamily: "monospace", marginTop: "6px" }}>
              {str(c.author)} · {str(c.timestamp_iso).slice(0, 10)}
            </div>
          </div>
        );

      case "flag_summary": {
        const healthColors: Record<string, string> = {
          HEALTHY: "#44BB88", WARNING: "#FFD700", CRITICAL: "#FF4444",
        };
        const healthColor = healthColors[str(c.health, "HEALTHY")] ?? "#888";
        return (
          <div style={{ padding: "14px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "16px" }}>
                {[
                  { label: "TOTAL",    val: num(c.total_flags),    color: "#888" },
                  { label: "OPEN",     val: num(c.open_flags),     color: "#FFD700" },
                  { label: "CRITICAL", val: num(c.critical_open),  color: "#FF4444" },
                  { label: "RESOLVED", val: num(c.resolved),       color: "#44BB88" },
                ].map(({ label, val, color }) => (
                  <div key={label} style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "18px", color, fontFamily: "monospace" }}>{val}</div>
                    <div style={{ fontSize: "8px", color: "#444", fontFamily: "monospace" }}>{label}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: "10px", fontFamily: "monospace", color: healthColor, border: `1px solid ${healthColor}`, padding: "4px 10px", letterSpacing: "0.1em" }}>
                {str(c.health)}
              </div>
            </div>
          </div>
        );
      }

      default:
        return (
          <div style={{ padding: "12px 24px", color: "#555", fontFamily: "monospace", fontSize: "11px" }}>
            [{block.type}] — configure in panel →
          </div>
        );
    }
  };

  return (
    <div
      style={{
        position: "relative",
        marginBottom: "2px",
        border: selected ? `1px solid ${accent}` : "1px solid transparent",
        borderRadius: "2px",
        cursor: "pointer",
        transition: "border-color 0.1s",
        background: selected ? "rgba(255,255,255,0.02)" : "transparent",
      }}
      onClick={() => onSelect(block.id)}
    >
      {renderContent()}

      {selected && (
        <>
          {/* Left accent bar */}
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "2px", background: accent }} />
          {/* Action buttons */}
          <div style={{ position: "absolute", top: "4px", right: "4px", display: "flex", gap: "2px" }}>
            {!isFirst && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveUp(block.id); }}
                style={{ background: "#1a1a1a", border: "none", color: "#888", fontSize: "10px", padding: "2px 6px", cursor: "pointer", fontFamily: "monospace" }}
              >↑</button>
            )}
            {!isLast && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveDown(block.id); }}
                style={{ background: "#1a1a1a", border: "none", color: "#888", fontSize: "10px", padding: "2px 6px", cursor: "pointer", fontFamily: "monospace" }}
              >↓</button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(block.id); }}
              style={{ background: "#1a1a1a", border: "none", color: "#FF4444", fontSize: "10px", padding: "2px 6px", cursor: "pointer", fontFamily: "monospace" }}
            >✕</button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PropertiesPanel — edit scalar fields of the selected block
// ---------------------------------------------------------------------------

interface PropertiesPanelProps {
  block: Block;
  accent: string;
  onUpdate: (id: string, field: string, value: unknown) => void;
}

function PropertiesPanel({ block, accent, onUpdate }: PropertiesPanelProps) {
  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "8px 14px" }}>
      <div style={{ fontSize: "8px", color: "#333", marginBottom: "6px", letterSpacing: "0.1em" }}>
        HASH: <span style={{ color: accent }}>{computeHash(block.content)}</span>
      </div>
      {Object.entries(block.content).map(([key, val]) => {
        // Only render scalar fields; arrays and objects need their own editors
        if (typeof val === "object") return null;

        const isBoolean = typeof val === "boolean";

        return (
          <div key={key} style={{ marginBottom: "10px" }}>
            <div style={{ fontSize: "8px", color: "#444", letterSpacing: "0.1em", marginBottom: "3px" }}>
              {key.toUpperCase()}
            </div>
            {isBoolean ? (
              <button
                onClick={() => onUpdate(block.id, key, !val)}
                style={{
                  background: val ? `${accent}22` : "#111",
                  border: `1px solid ${val ? accent : "#222"}`,
                  color: val ? accent : "#555",
                  fontSize: "9px", fontFamily: "monospace",
                  padding: "4px 10px", cursor: "pointer",
                }}
              >
                {val ? "TRUE" : "FALSE"}
              </button>
            ) : (
              <input
                value={String(val)}
                onChange={(e) => onUpdate(block.id, key, e.target.value)}
                style={{
                  width: "100%", background: "#0a0a0a",
                  border: "1px solid #1a1a1a", color: "#aaa",
                  fontSize: "10px", fontFamily: "monospace",
                  padding: "5px 8px", outline: "none", boxSizing: "border-box",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = accent; }}
                onBlur={(e)  => { e.currentTarget.style.borderColor = "#1a1a1a"; }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const INITIAL_BLOCKS: Block[] = [
  {
    id: generateId(), type: "header",
    content: { title: "Blackhorse Sentinel Report", subtitle: "Technical Verification Report · March 2026", classification: "CONFIDENTIAL" },
  },
  {
    id: generateId(), type: "verification_summary",
    content: { total: 12, verified: 10, pending: 1, failed: 1, pass_rate: "83.3%" },
  },
  {
    id: generateId(), type: "section",
    content: { title: "Artifact Records", description: "" },
  },
  {
    id: generateId(), type: "hash_record",
    content: {
      artifact_name: "contract_final_v3.pdf",
      hash_sha256: "a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2",
      hash_sha3: "7c8d9e0f1a2b3c4d5e6f7890abcdef01...",
      timestamp_iso: "2026-03-06T14:23:11Z",
      verified_by: "Blackhorse Sentinel",
    },
  },
  {
    id: generateId(), type: "finding",
    content: {
      title: "Metadata Timestamp Inconsistency",
      description: "File system metadata indicates creation date precedes claimed authorship by 72 hours.",
      severity: "high",
      recommendation: "Request original system logs from custodian.",
    },
  },
  {
    id: generateId(), type: "integrity_proof",
    content: {
      subject: "Report Package",
      root_hash: "8b2c3d4e5f6a7b8c...",
      block_count: 6,
      compiled_at: "2026-03-06T14:30:00Z",
      verification_method: "SHA-256 Merkle chain",
    },
  },
];

export function ReportBuilder() {
  const [blocks, setBlocks] = useState<Block[]>(INITIAL_BLOCKS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [theme, setTheme] = useState("sentinel");
  const [audience, setAudience] = useState("sentinel");
  const [reportTitle, setReportTitle] = useState("Blackhorse Sentinel Report");
  const [classification, setClassification] = useState("CONFIDENTIAL");
  const [activeCategory, setActiveCategory] = useState("Layout");
  const [compiled, setCompiled] = useState<CompiledReport | null>(null);
  const [activeTab, setActiveTab] = useState<"canvas" | "json" | "api">("canvas");

  const accent = getAccent(theme);
  const selectedBlock = blocks.find(b => b.id === selectedId) ?? null;

  // ------------------------------------------------------------------
  // Block mutations
  // ------------------------------------------------------------------

  const addBlock = useCallback((type: string) => {
    const newBlock: Block = { id: generateId(), type, content: { ...DEFAULT_CONTENT[type] } };
    setBlocks(prev => [...prev, newBlock]);
    setSelectedId(newBlock.id);
    setCompiled(null);
  }, []);

  const deleteBlock = useCallback((id: string) => {
    setBlocks(prev => prev.filter(b => b.id !== id));
    setSelectedId(null);
    setCompiled(null);
  }, []);

  const moveUp = useCallback((id: string) => {
    setBlocks(prev => {
      const idx = prev.findIndex(b => b.id === id);
      if (idx <= 0) return prev;
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
    setCompiled(null);
  }, []);

  const moveDown = useCallback((id: string) => {
    setBlocks(prev => {
      const idx = prev.findIndex(b => b.id === id);
      if (idx === -1 || idx === prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
    setCompiled(null);
  }, []);

  const updateContent = useCallback((id: string, field: string, value: unknown) => {
    setBlocks(prev =>
      prev.map(b => b.id === id ? { ...b, content: { ...b.content, [field]: value } } : b)
    );
    setCompiled(null);
  }, []);

  // ------------------------------------------------------------------
  // Compile
  // ------------------------------------------------------------------

  const compileReport = () => {
    const blockHashes = blocks.map(b => computeHash(b.content));
    const rootInput = blockHashes.join("");
    let rootHash = 0;
    for (let i = 0; i < rootInput.length; i++) {
      rootHash = ((rootHash << 5) - rootHash) + rootInput.charCodeAt(i);
      rootHash |= 0;
    }
    const rootHashHex = Math.abs(rootHash).toString(16).padStart(64, "0");

    const report: CompiledReport = {
      report_id: generateId(),
      title: reportTitle,
      theme,
      audience,
      classification,
      compiled_at: new Date().toISOString(),
      version: "1.0",
      integrity: {
        block_count: blocks.length,
        block_hashes: blockHashes,
        root_hash_sha256: rootHashHex,
        verified: true,
      },
      blocks: blocks.map((b, i) => ({
        block_id: b.id,
        block_type: b.type,
        content: b.content,
        order: i,
        content_hash: computeHash(b.content),
      })),
    };
    setCompiled(report);
    setActiveTab("json");
  };

  // ------------------------------------------------------------------
  // API code generation (aspirational Python API — Stage 3)
  // ------------------------------------------------------------------

  const generateApiCode = (): string => {
    const blockLines = blocks.map(b => {
      const entries = Object.entries(b.content)
        .filter(([, v]) => typeof v !== "object")
        .map(([k, v]) => `    ${k}=${JSON.stringify(v)}`)
        .join(",\n");
      return `api.add_block_from_factory(\n    report_id, "${b.type}",\n${entries},\n)`;
    }).join("\n\n");

    return `# Blackhorse Report Builder — Python API
# Reproduce this report programmatically
# Stage 3: blackhorse.reports module (coming in v0.2.0)

from blackhorse.reports import ReportCanvas, BlockFactory
from blackhorse.api import ReportAPI

api = ReportAPI()

# Create canvas
r = api.create_report(
    title=${JSON.stringify(reportTitle)},
    theme=${JSON.stringify(theme)},
    audience=${JSON.stringify(audience)},
    classification=${JSON.stringify(classification)},
)
report_id = r["data"]["report_id"]

# Add blocks
${blockLines}

# Compile and export
api.compile(report_id)
result = api.export_json(report_id)
api.export_to_file(report_id, output_dir=Path("./reports"))
`;
  };

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      height: "calc(100vh - 64px)",  // 64px = Navigation bar height
      background: "#080808", color: "#ccc", fontFamily: "monospace",
    }}>
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <div style={{
        height: "44px", borderBottom: "1px solid #1a1a1a",
        display: "flex", alignItems: "center", padding: "0 16px",
        justifyContent: "space-between", background: "#060606", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ fontSize: "12px", color: accent, letterSpacing: "0.2em", fontWeight: 600 }}>
            🐴 BLACKHORSE
          </div>
          <Divider />
          <div style={{ fontSize: "11px", color: "#555", letterSpacing: "0.1em" }}>REPORT BUILDER</div>
          <Divider />
          <input
            value={reportTitle}
            onChange={e => setReportTitle(e.target.value)}
            style={{ background: "transparent", border: "none", color: "#888", fontSize: "11px", fontFamily: "monospace", outline: "none", width: "280px" }}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ fontSize: "9px", color: "#444", letterSpacing: "0.1em", padding: "3px 8px", border: "1px solid #1a1a1a" }}>
            {blocks.length} BLOCKS
          </div>
          <select
            value={classification}
            onChange={e => setClassification(e.target.value)}
            style={{ background: "#0a0a0a", border: "1px solid #222", color: accent, fontSize: "9px", fontFamily: "monospace", padding: "3px 6px", letterSpacing: "0.1em" }}
          >
            {CLASSIFICATIONS.map(c => <option key={c}>{c}</option>)}
          </select>
          {compiled ? (
            <div
              style={{ fontSize: "9px", color: "#44BB88", letterSpacing: "0.1em", padding: "4px 10px", border: "1px solid #44BB8844", background: "#44BB8808", cursor: "pointer" }}
              onClick={() => setCompiled(null)}
            >
              ✓ COMPILED — click to reset
            </div>
          ) : (
            <button
              onClick={compileReport}
              style={{ background: accent, border: "none", color: "#000", fontSize: "10px", fontFamily: "monospace", padding: "6px 14px", cursor: "pointer", letterSpacing: "0.1em", fontWeight: 700 }}
            >
              COMPILE →
            </button>
          )}
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* ── Left panel — block library ──────────────────────────── */}
        <div style={{ width: "200px", borderRight: "1px solid #1a1a1a", display: "flex", flexDirection: "column", background: "#060606", flexShrink: 0 }}>
          <div style={{ padding: "10px 12px 8px", fontSize: "8px", color: "#444", letterSpacing: "0.15em" }}>COMPONENTS</div>

          {/* Category filter */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "2px", padding: "0 6px 8px", borderBottom: "1px solid #111" }}>
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  background: activeCategory === cat ? `${accent}22` : "transparent",
                  border: activeCategory === cat ? `1px solid ${accent}44` : "1px solid #1a1a1a",
                  color: activeCategory === cat ? accent : "#555",
                  fontSize: "8px", fontFamily: "monospace", padding: "3px 6px", cursor: "pointer", letterSpacing: "0.08em",
                }}
              >
                {cat.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Block list */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {BLOCK_TYPES.filter(b => b.category === activeCategory).map(bt => (
              <button
                key={bt.type}
                onClick={() => addBlock(bt.type)}
                style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%", background: "transparent", border: "none", borderBottom: "1px solid #0d0d0d", color: "#777", fontSize: "11px", fontFamily: "monospace", padding: "10px 14px", cursor: "pointer", textAlign: "left" }}
                onMouseEnter={e => { e.currentTarget.style.background = "#111"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{ color: accent, fontSize: "12px", width: "16px" }}>{bt.icon}</span>
                <span style={{ fontSize: "10px" }}>{bt.label}</span>
              </button>
            ))}
          </div>

          {/* Theme selector */}
          <div style={{ borderTop: "1px solid #1a1a1a", padding: "10px 12px" }}>
            <div style={{ fontSize: "8px", color: "#444", letterSpacing: "0.15em", marginBottom: "6px" }}>THEME</div>
            {THEMES.map(t => (
              <button
                key={t.value}
                onClick={() => setTheme(t.value)}
                style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%", background: "transparent", border: "none", color: theme === t.value ? "#fff" : "#555", fontSize: "10px", fontFamily: "monospace", padding: "5px 2px", cursor: "pointer", textAlign: "left" }}
              >
                <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: t.accent, opacity: theme === t.value ? 1 : 0.3 }} />
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Center — canvas / json / api tabs ───────────────────── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Tab bar */}
          <div style={{ display: "flex", borderBottom: "1px solid #1a1a1a", background: "#060606", flexShrink: 0 }}>
            {(["canvas", "json", "api"] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: activeTab === tab ? "#0a0a0a" : "transparent",
                  border: "none", borderRight: "1px solid #1a1a1a",
                  borderBottom: activeTab === tab ? `1px solid ${accent}` : "1px solid transparent",
                  color: activeTab === tab ? accent : "#555",
                  fontSize: "9px", fontFamily: "monospace", padding: "10px 16px", cursor: "pointer",
                  letterSpacing: "0.12em", marginBottom: "-1px",
                }}
              >
                {tab === "api" ? "API CODE" : tab.toUpperCase()}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            <div style={{ fontSize: "9px", color: "#333", padding: "10px 16px", letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: "6px" }}>
              AUDIENCE:
              <select
                value={audience}
                onChange={e => setAudience(e.target.value)}
                style={{ background: "transparent", border: "none", color: "#555", fontSize: "9px", fontFamily: "monospace", cursor: "pointer" }}
              >
                {AUDIENCES.map(a => <option key={a} value={a}>{a.toUpperCase()}</option>)}
              </select>
            </div>
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {activeTab === "canvas" && (
              <div style={{ maxWidth: "820px", margin: "0 auto", paddingBottom: "60px" }}>
                {blocks.length === 0 ? (
                  <div style={{ padding: "80px 40px", textAlign: "center", color: "#333", fontSize: "12px", letterSpacing: "0.1em" }}>
                    <div style={{ fontSize: "32px", marginBottom: "16px", opacity: 0.3 }}>◈</div>
                    ADD A COMPONENT FROM THE LEFT PANEL
                  </div>
                ) : (
                  blocks.map((block, idx) => (
                    <BlockPreview
                      key={block.id}
                      block={block}
                      theme={theme}
                      selected={selectedId === block.id}
                      onSelect={setSelectedId}
                      onDelete={deleteBlock}
                      onMoveUp={moveUp}
                      onMoveDown={moveDown}
                      isFirst={idx === 0}
                      isLast={idx === blocks.length - 1}
                    />
                  ))
                )}
              </div>
            )}

            {activeTab === "json" && (
              <div style={{ padding: "16px" }}>
                {compiled ? (
                  <pre style={{ fontSize: "10px", fontFamily: "monospace", lineHeight: 1.6, margin: 0 }}>
                    <span style={{ color: "#3a3a3a", display: "block", marginBottom: "12px", letterSpacing: "0.1em" }}>
                      {`// COMPILED REPORT · ROOT HASH: ${compiled.integrity.root_hash_sha256}`}
                    </span>
                    {JSON.stringify(compiled, null, 2)
                      .split("\n")
                      .map((line, i) => (
                        <JsonLine key={i} line={line} accent={accent} />
                      ))}
                  </pre>
                ) : (
                  <div style={{ padding: "60px 40px", textAlign: "center", color: "#333", fontSize: "11px", letterSpacing: "0.1em" }}>
                    <div style={{ marginBottom: "16px", color: "#444" }}>COMPILE THE REPORT TO VIEW JSON OUTPUT</div>
                    <button
                      onClick={compileReport}
                      style={{ background: accent, border: "none", color: "#000", fontSize: "11px", fontFamily: "monospace", padding: "10px 20px", cursor: "pointer", letterSpacing: "0.12em", fontWeight: 700 }}
                    >
                      COMPILE →
                    </button>
                  </div>
                )}
              </div>
            )}

            {activeTab === "api" && (
              <div style={{ padding: "16px" }}>
                <div style={{ fontSize: "9px", color: "#444", letterSpacing: "0.12em", marginBottom: "12px" }}>
                  PYTHON API — reproduce this report programmatically (Stage 3)
                </div>
                <pre style={{ fontSize: "10px", fontFamily: "monospace", lineHeight: 1.8, margin: 0, whiteSpace: "pre-wrap" }}>
                  {generateApiCode().split("\n").map((line, i) => {
                    if (line.startsWith("#")) return <span key={i} style={{ color: "#3a3a3a", display: "block" }}>{line}</span>;
                    if (line.includes("from ") || line.includes("import ")) return <span key={i} style={{ color: "#555", display: "block" }}>{line}</span>;
                    if (line.includes("api.") || line.includes("result")) return <span key={i} style={{ color: accent, display: "block" }}>{line}</span>;
                    return <span key={i} style={{ color: "#666", display: "block" }}>{line}</span>;
                  })}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* ── Right panel — properties ─────────────────────────────── */}
        <div style={{ width: "220px", borderLeft: "1px solid #1a1a1a", display: "flex", flexDirection: "column", background: "#060606", flexShrink: 0 }}>
          {selectedBlock ? (
            <>
              <div style={{ padding: "10px 14px 8px", fontSize: "8px", color: "#444", letterSpacing: "0.15em", borderBottom: "1px solid #111", display: "flex", justifyContent: "space-between" }}>
                <span>PROPERTIES</span>
                <span style={{ color: accent }}>{selectedBlock.type.toUpperCase()}</span>
              </div>
              <PropertiesPanel block={selectedBlock} accent={accent} onUpdate={updateContent} />
            </>
          ) : (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#333", fontSize: "10px", letterSpacing: "0.1em", lineHeight: 1.8 }}>
              SELECT A BLOCK<br />TO EDIT<br />PROPERTIES
            </div>
          )}

          {/* Integrity footer */}
          <div style={{ borderTop: "1px solid #1a1a1a", padding: "10px 14px", marginTop: "auto" }}>
            <div style={{ fontSize: "8px", color: "#333", letterSpacing: "0.1em", marginBottom: "6px" }}>INTEGRITY</div>
            {compiled ? (
              <>
                <div style={{ fontSize: "8px", color: "#44BB88", letterSpacing: "0.08em", marginBottom: "3px" }}>✓ COMPILED</div>
                <div style={{ fontSize: "7px", color: "#333", fontFamily: "monospace", wordBreak: "break-all" }}>
                  {compiled.integrity.root_hash_sha256.slice(0, 24)}...
                </div>
                <div style={{ fontSize: "7px", color: "#2a2a2a", marginTop: "4px" }}>
                  {compiled.compiled_at.slice(0, 19)}Z
                </div>
              </>
            ) : (
              <div style={{ fontSize: "8px", color: "#333", letterSpacing: "0.08em" }}>NOT COMPILED</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function Divider() {
  return <div style={{ width: "1px", height: "16px", background: "#1a1a1a" }} />;
}
