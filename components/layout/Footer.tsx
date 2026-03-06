/**
 * Footer — site-wide footer for Blackhorse Sentinel.
 */

import Link from "next/link";
import { Shield } from "lucide-react";

const FOOTER_LINKS = {
  Platform: [
    { href: "/artifacts",     label: "Artifacts" },
    { href: "/artifacts/new", label: "Ingest" },
    { href: "/#trust",        label: "Trust Model" },
    { href: "/#proof",        label: "Proof Explorer" },
  ],
  Enterprise: [
    { href: "/#enterprise",  label: "Enterprise" },
    { href: "/#sla",         label: "SLA" },
    { href: "/#compliance",  label: "Compliance" },
    { href: "/#security",    label: "Security" },
  ],
  Developers: [
    { href: "/docs",       label: "Documentation" },
    { href: "/#agents",    label: "Agent API" },
    { href: "/#changelog", label: "Changelog" },
    { href: "/api/health", label: "Status" },
  ],
  Company: [
    { href: "/#contact", label: "Contact" },
    { href: "/#about",   label: "About" },
  ],
} as const;

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
          {/* Brand */}
          <div className="lg:col-span-1">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-sentinel-navy">
                <Shield className="h-4 w-4 text-white" />
              </div>
              <span className="text-sm font-bold text-sentinel-navy">Sentinel</span>
            </div>
            <p className="mt-3 text-xs text-gray-500 leading-relaxed">
              Trust, with receipts.<br />
              Enterprise verification infrastructure<br />
              for the AI age.
            </p>
            <p className="mt-4 text-[11px] text-gray-400">
              Powered by the{" "}
              <span className="font-medium text-gray-600">Blackhorse Protocol</span>
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(FOOTER_LINKS).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                {category}
              </h3>
              <ul className="mt-3 space-y-2">
                {links.map(({ href, label }) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-sm text-gray-600 hover:text-sentinel-accent transition-colors"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 border-t border-gray-100 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-gray-400">
            © 2026 Blackhorse Sentinel. All rights reserved.
          </p>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <Link href="/#privacy" className="hover:text-gray-600 transition-colors">Privacy</Link>
            <Link href="/#terms" className="hover:text-gray-600 transition-colors">Terms</Link>
            <Link href="/#security" className="hover:text-gray-600 transition-colors">Security</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
