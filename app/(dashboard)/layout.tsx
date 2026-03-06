/**
 * Dashboard layout — wraps all authenticated dashboard surfaces.
 *
 * At Stage 1: navigation is present, auth is not yet wired (Stage 4).
 * TODO Stage 4: Add Clerk <ClerkProvider> and middleware auth guard here.
 */

import { Navigation } from "@/components/layout/Navigation";
import { Footer } from "@/components/layout/Footer";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-sentinel-gray pt-16">
        {children}
      </div>
      <Footer />
    </>
  );
}
