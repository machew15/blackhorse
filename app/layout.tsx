/**
 * Root layout — wraps every page in Blackhorse Sentinel.
 *
 * Loads Inter (body) and JetBrains Mono (hash displays) from Google Fonts
 * via next/font (zero layout shift, self-hosted by Next.js).
 */

import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Blackhorse Sentinel — Trust, with receipts.",
    template: "%s | Blackhorse Sentinel",
  },
  description:
    "Enterprise verification infrastructure for the AI age. Cryptographically sound. Auditably true.",
  keywords: [
    "verification",
    "trust",
    "cryptography",
    "SHA-256",
    "SHA-3",
    "artifact hashing",
    "integrity proofs",
    "enterprise",
  ],
  openGraph: {
    siteName: "Blackhorse Sentinel",
    locale: "en_US",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
