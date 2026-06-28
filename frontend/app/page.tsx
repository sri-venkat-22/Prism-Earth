import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const API_DOCS_URL = process.env.NEXT_PUBLIC_API_DOCS_URL ?? "http://localhost:8000/docs";
const API_HEALTH_URL =
  process.env.NEXT_PUBLIC_API_HEALTH_URL ?? "http://localhost:8000/api/v1/health";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <p className="text-sm font-medium text-muted-foreground">Phase 0 · Scaffold</p>
          <CardTitle>Prism Earth</CardTitle>
          <CardDescription>
            Deterministic, citation-backed geospatial intelligence for India. This is the
            placeholder shell — pages and components arrive in Phase 6.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <a
            href={API_DOCS_URL}
            className={cn(buttonVariants({ variant: "default" }))}
            target="_blank"
            rel="noreferrer"
          >
            API Docs
          </a>
          <a
            href={API_HEALTH_URL}
            className={cn(buttonVariants({ variant: "outline" }))}
            target="_blank"
            rel="noreferrer"
          >
            Backend Health
          </a>
        </CardContent>
      </Card>
    </main>
  );
}
