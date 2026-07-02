"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";

import { BackendStatus } from "@/components/backend-status";
import { Logo } from "@/components/layout/logo";
import { DEV_TOOLS } from "@/lib/dev";
import { cn } from "@/lib/utils";

const DOCS_URL = process.env.NEXT_PUBLIC_API_DOCS_URL ?? "http://localhost:8000/docs";

// Normal-user navigation is deliberately just Ask + Dashboard, plus marketing
// anchors (Use Cases / FAQ, mireye-style — nav links that scroll to homepage
// sections) and Documentation. Explore and System are developer tools: they are
// appended ONLY when DEV_TOOLS is on, so for normal users they never enter the
// rendered DOM (SRS §12 nav rule).
type NavItem = { href: string; label: string; kind?: "external" | "anchor" };

const BASE_ITEMS: NavItem[] = [
  { href: "/ask", label: "Ask" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/#use-cases", label: "Use Cases", kind: "anchor" },
  { href: "/#faq", label: "FAQ", kind: "anchor" },
];

const DEV_ITEMS: NavItem[] = [
  { href: "/explore", label: "Explore" },
  { href: "/system", label: "System" },
];

const NAV_ITEMS: NavItem[] = [
  ...BASE_ITEMS,
  ...(DEV_TOOLS ? DEV_ITEMS : []),
  { href: DOCS_URL, label: "Documentation", kind: "external" },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-[1240px] items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" aria-label="Prism Earth home" className="shrink-0">
          <Logo />
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) =>
            item.kind === "external" ? (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {item.label}
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
              </a>
            ) : item.kind === "anchor" ? (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {item.label}
              </Link>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(pathname, item.href) ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm transition-colors",
                  isActive(pathname, item.href)
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            ),
          )}
        </nav>

        <div className="flex items-center gap-3">
          <BackendStatus className="hidden lg:inline-flex" />
          <Link
            href="/ask"
            className="hidden items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-transform duration-200 ease-expo hover:-translate-y-0.5 sm:inline-flex"
          >
            Try <span className="font-mono">/ask</span>
          </Link>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-accent md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {open && (
        <nav
          aria-label="Mobile"
          className="border-t border-border/70 bg-background px-5 py-4 md:hidden"
        >
          <div className="mb-3">
            <BackendStatus />
          </div>
          <div className="grid gap-1">
            {NAV_ITEMS.map((item) =>
              item.kind === "external" ? (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setOpen(false)}
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  {item.label}
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                </a>
              ) : item.kind === "anchor" ? (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  {item.label}
                </Link>
              ) : (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActive(pathname, item.href) ? "page" : undefined}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm",
                    isActive(pathname, item.href)
                      ? "bg-accent font-medium text-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ),
            )}
            <Link
              href="/ask"
              onClick={() => setOpen(false)}
              className="mt-2 inline-flex items-center justify-center gap-1.5 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
            >
              Try <span className="font-mono">/ask</span>
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
