"use client";

import { ServerCog } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ConnectorsHealth } from "@/features/system/connectors-health";

export default function SystemPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="System"
        icon={<ServerCog className="h-7 w-7 text-brand" />}
        description="Live health of the API, its dependencies, and every data connector — from /health and /health/connectors. Auto-refreshes."
      />
      <ConnectorsHealth />
    </div>
  );
}
