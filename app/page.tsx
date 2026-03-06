/**
 * Homepage — Blackhorse Sentinel marketing site.
 *
 * Visual language: dark navy, institutional, trustworthy.
 * "Stripe meets legal tech meets security infrastructure."
 *
 * Sections:
 *   1. Hero          — tagline + CTAs + live verification receipt card
 *   2. How it works  — 4-step pipeline
 *   3. Tech specs    — cryptographic guarantees
 *   4. Trust signals — compliance surface (placeholders for Stage 5)
 *   5. CTA           — call to action
 */

import Link from "next/link";
import {
  Shield,
  ArrowRight,
  FileText,
  Hash,
  Link2,
  FileOutput,
  CheckCircle,
  Lock,
  Clock,
  Database,
  ChevronRight,
} from "lucide-react";
import { Navigation } from "@/components/layout/Navigation";
import { Footer } from "@/components/layout/Footer";

// ---------------------------------------------------------------------------
// Static data for sections
// ---------------------------------------------------------------------------

const STEPS = [
  {
    step: "01",
    Icon: FileText,
    title: "Ingest Artifacts",
    description:
      "Upload PDFs, paste URLs, drop images, or stream structured data. Every format accepted.",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
  },
  {
    step: "02",
    Icon: Hash,
    title: "Hash + Timestamp",
    description:
      "SHA-256 and SHA-3-512 dual-hash computed server-side. ISO 8601 timestamp assigned. Nonce-salted.",
    color: "text-purple-400",
    bg: "bg-purple-500/10",
  },
  {
    step: "03",
    Icon: Link2,
    title: "Link Evidence",
    description:
      "Connect assertions to supporting artifacts. Build structured verification graphs with provable chains.",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
  },
  {
    step: "04",
    Icon: FileOutput,
    title: "Export Report",
    description:
      "Generate versioned Technical Verification Reports with cryptographic integrity proofs.",
    color: "text-amber-400",
    bg: "bg-amber-500/10",
  },
] as const;

const TECH_BADGES = [
  { label: "SHA-256", detail: "256-bit digest" },
  { label: "SHA-3-512", detail: "512-bit quantum-transition hash" },
  { label: "ISO 8601", detail: "Millisecond-precision timestamps" },
  { label: "Nonce-salted", detail: "Server-assigned uniqueness" },
  { label: "Server-side only", detail: "Client hashes never trusted" },
  { label: "Post-quantum ready", detail: "BHL + Dilithium at Stage 6" },
] as const;

const COMPLIANCE_ITEMS = [
  { label: "SOC 2 Type II",  status: "Stage 5" },
  { label: "HIPAA Aligned",  status: "Stage 5" },
  { label: "GDPR Tooling",   status: "Stage 5" },
  { label: "ISO 27001",      status: "Stage 5" },
] as const;

// ---------------------------------------------------------------------------
// Hero receipt card (static mock)
// ---------------------------------------------------------------------------

function VerificationReceiptCard() {
  return (
    <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-gradient-to-br from-[#1A2D45] to-[#142236] p-6 shadow-2xl shadow-black/40">
      {/* Header row */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-sentinel-accent" />
          <span className="text-xs font-bold uppercase tracking-widest text-gray-400">
            Verification Receipt
          </span>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-emerald-900/50 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 ring-1 ring-emerald-500/30">
          <span className="h-1.5 w-1.5 rounded-full bg-sentinel-green animate-pulse" />
          VERIFIED
        </span>
      </div>

      {/* Fields */}
      <div className="space-y-3">
        <ReceiptField label="Artifact ID" value="a3f9b2c1-d4e5-6789-abcd-ef012345" mono />
        <ReceiptField
          label="SHA-256"
          value="a3f9b2c1d4e5f6789abcdef012345678…9012345"
          mono
          highlight
        />
        <ReceiptField
          label="SHA-3-512"
          value="7d8c9e0f1a2b3c4d5e6f789012345678…abcdef01"
          mono
          highlight
        />
        <ReceiptField label="Timestamp" value="2026-03-06T18:45:32.891Z" mono />
        <ReceiptField label="Nonce" value="f0e1d2c3b4a59687…" mono />
      </div>

      {/* Footer */}
      <div className="mt-5 flex items-center justify-between border-t border-white/5 pt-4">
        <span className="text-[11px] text-gray-500 font-mono">
          Blackhorse Protocol v0.1
        </span>
        <span className="flex items-center gap-1 text-[11px] text-emerald-400">
          <CheckCircle className="h-3 w-3" />
          Integrity verified
        </span>
      </div>
    </div>
  );
}

function ReceiptField({
  label,
  value,
  mono = false,
  highlight = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-0.5">
        {label}
      </p>
      <p
        className={`text-xs leading-relaxed ${
          mono ? "font-mono" : ""
        } ${highlight ? "text-blue-300" : "text-gray-300"}`}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  return (
    <>
      <Navigation />

      <main>
        {/* ----------------------------------------------------------------
            Hero
            ---------------------------------------------------------------- */}
        <section
          id="hero"
          className="relative overflow-hidden bg-sentinel-hero pt-32 pb-24 lg:pt-40 lg:pb-32"
          aria-labelledby="hero-heading"
        >
          {/* Subtle grid overlay */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
          />

          <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid items-center gap-12 lg:grid-cols-2">
              {/* Left: copy */}
              <div className="animate-fade-in">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sentinel-accent/30 bg-sentinel-accent/10 px-3 py-1 text-xs font-medium text-sentinel-accent">
                  <span className="h-1.5 w-1.5 rounded-full bg-sentinel-accent" />
                  Stage 1 — Core Verification Engine
                </div>

                <h1
                  id="hero-heading"
                  className="text-5xl font-bold leading-tight text-white lg:text-6xl xl:text-7xl"
                >
                  Trust,{" "}
                  <span className="bg-gradient-to-r from-sentinel-accent to-blue-300 bg-clip-text text-transparent">
                    with receipts.
                  </span>
                </h1>

                <p className="mt-6 text-lg leading-relaxed text-gray-300 max-w-xl">
                  Enterprise verification infrastructure for the AI age.
                  Ingest artifacts, hash them cryptographically, timestamp them
                  immutably, and export verifiable proof — every time.
                </p>

                <div className="mt-8 flex flex-wrap gap-3">
                  <Link
                    href="/artifacts/new"
                    className="inline-flex items-center gap-2 rounded-lg bg-sentinel-accent px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
                  >
                    Start Verifying
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/docs"
                    className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/5"
                  >
                    View Documentation
                  </Link>
                </div>

                <div className="mt-8 flex items-center gap-6 text-xs text-gray-500">
                  <span className="flex items-center gap-1.5">
                    <Lock className="h-3.5 w-3.5 text-gray-600" />
                    Server-side hashing only
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-gray-600" />
                    Millisecond timestamps
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-gray-600" />
                    SHA-256 + SHA-3-512
                  </span>
                </div>
              </div>

              {/* Right: receipt card */}
              <div className="flex justify-center lg:justify-end animate-slide-up">
                <VerificationReceiptCard />
              </div>
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------------
            Trust signal bar
            ---------------------------------------------------------------- */}
        <section className="border-y border-gray-100 bg-white py-6">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
              <span className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                Compliance roadmap
              </span>
              {COMPLIANCE_ITEMS.map(({ label, status }) => (
                <span
                  key={label}
                  className="flex items-center gap-2 text-sm text-gray-400"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-gray-300" />
                  {label}
                  <span className="text-xs text-gray-300 font-mono">{status}</span>
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------------
            How it works — 4 steps
            ---------------------------------------------------------------- */}
        <section
          id="trust"
          className="py-24 bg-sentinel-gray"
          aria-labelledby="how-it-works-heading"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-14">
              <h2
                id="how-it-works-heading"
                className="text-3xl font-bold text-sentinel-navy lg:text-4xl"
              >
                How it works
              </h2>
              <p className="mt-4 text-gray-500 max-w-2xl mx-auto">
                A four-stage pipeline that transforms raw artifacts into
                cryptographically verifiable trust records.
              </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map(({ step, Icon, title, description, color, bg }) => (
                <div
                  key={step}
                  className="relative rounded-xl border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className={`mb-4 inline-flex rounded-lg p-2.5 ${bg}`}>
                    <Icon className={`h-5 w-5 ${color}`} />
                  </div>
                  <div className="mb-2 font-mono text-xs font-bold text-gray-300">
                    {step}
                  </div>
                  <h3 className="text-base font-semibold text-sentinel-navy mb-2">
                    {title}
                  </h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------------
            Technical specs
            ---------------------------------------------------------------- */}
        <section
          id="security"
          className="py-24 bg-white"
          aria-labelledby="tech-specs-heading"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
              <div>
                <h2
                  id="tech-specs-heading"
                  className="text-3xl font-bold text-sentinel-navy lg:text-4xl"
                >
                  Cryptographic guarantees
                  <br />
                  <span className="text-gray-400">you can build on.</span>
                </h2>
                <p className="mt-4 text-gray-500 leading-relaxed">
                  Every artifact is anchored with a dual-hash strategy: SHA-256
                  for broad compatibility and SHA-3-512 as the quantum-transition
                  hash. At Stage 6, SHA-3-512 feeds into BHL encoding before
                  Dilithium signing via the Blackhorse Protocol.
                </p>
                <Link
                  href="/docs"
                  className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-sentinel-accent hover:underline"
                >
                  Read the technical documentation
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>

              <div className="flex flex-wrap gap-3">
                {TECH_BADGES.map(({ label, detail }) => (
                  <div
                    key={label}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 hover:border-sentinel-accent/40 hover:bg-blue-50 transition-colors"
                  >
                    <p className="text-sm font-semibold text-sentinel-navy font-mono">
                      {label}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">{detail}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------------
            Final CTA
            ---------------------------------------------------------------- */}
        <section
          className="bg-sentinel-navy py-24"
          aria-labelledby="cta-heading"
        >
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <h2
              id="cta-heading"
              className="text-3xl font-bold text-white lg:text-4xl"
            >
              Ready to build trust?
            </h2>
            <p className="mt-4 text-gray-300">
              Start ingesting artifacts and generating verification receipts in
              seconds. No credit card required.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                href="/artifacts/new"
                className="inline-flex items-center gap-2 rounded-lg bg-sentinel-accent px-8 py-3 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
              >
                Ingest your first artifact
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/artifacts"
                className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-8 py-3 text-sm font-semibold text-white hover:bg-white/5 transition-colors"
              >
                View dashboard
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
