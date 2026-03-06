/**
 * Navigation — top navigation bar for Blackhorse Sentinel.
 *
 * Fixed dark navy bar with the Sentinel logo, primary nav links, and a CTA.
 * Collapses to a hamburger menu on mobile (implementation deferred to Stage 2 UX).
 */

import Link from "next/link";
import { Shield } from "lucide-react";

const PRIMARY_LINKS = [
  { href: "/#trust",      label: "Trust" },
  { href: "/#proof",      label: "Proof" },
  { href: "/#enterprise", label: "Enterprise" },
  { href: "/docs",        label: "Docs" },
  { href: "/#security",   label: "Security" },
] as const;

/**
 * Primary navigation bar.
 * Server component — no client-side state required at this level.
 */
export function Navigation() {
  return (
    <nav
      className="fixed left-0 right-0 top-0 z-50 border-b border-white/10 bg-sentinel-navy/95 backdrop-blur-md"
      aria-label="Primary navigation"
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group" aria-label="Blackhorse Sentinel home">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sentinel-accent/20 ring-1 ring-sentinel-accent/40 group-hover:bg-sentinel-accent/30 transition-colors">
            <Shield className="h-4 w-4 text-sentinel-accent" />
          </div>
          <div className="leading-none">
            <span className="block text-[11px] font-bold uppercase tracking-[0.2em] text-gray-400">
              Blackhorse
            </span>
            <span className="block text-[15px] font-bold text-white tracking-tight">
              Sentinel
            </span>
          </div>
        </Link>

        {/* Primary links — hidden on mobile */}
        <div className="hidden items-center gap-1 md:flex">
          {PRIMARY_LINKS.map(({ href, label }) => (
            <Link
              key={label}
              href={href}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-white/5 hover:text-white"
            >
              {label}
            </Link>
          ))}
        </div>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <Link
            href="/artifacts"
            className="hidden text-sm font-medium text-gray-300 hover:text-white transition-colors sm:block"
          >
            Sign in
          </Link>
          <Link
            href="/artifacts/new"
            className="rounded-md bg-sentinel-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          >
            Start Free
          </Link>
        </div>
      </div>
    </nav>
  );
}
