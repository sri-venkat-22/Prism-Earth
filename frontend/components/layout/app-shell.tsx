import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/layout/logo";
import { Nav } from "@/components/layout/nav";

const DOCS_URL = process.env.NEXT_PUBLIC_API_DOCS_URL ?? "http://localhost:8000/docs";

/** Global page frame: top nav, main content, editorial footer. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col">
      <Nav />

      <main className="mx-auto w-full max-w-[1240px] flex-1 px-5 py-12 sm:px-8 sm:py-16">
        {children}
      </main>

      <footer className="border-t border-border/70">
        <div className="mx-auto flex w-full max-w-[1240px] flex-col gap-4 px-5 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <div className="space-y-2">
            <Logo />
            <p className="max-w-md text-[13px] leading-relaxed text-muted-foreground">
              Deterministic, citation-backed geospatial ground truth for India. Every value is
              sourced and traceable — never fabricated. Pilot region: Telangana.
            </p>
          </div>
          <div className="flex items-center gap-5 text-[13px] text-muted-foreground">
            <Link href="/ask" className="hover:text-foreground">
              Ask
            </Link>
            <Link href="/motion" className="hover:text-foreground">
              Motion
            </Link>
            <a href={DOCS_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
              Documentation
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
