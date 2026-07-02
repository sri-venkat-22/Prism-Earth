"use client";

import { Boxes, Compass, Database, Layers, MapPinned } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DatasetExplorer } from "@/features/explorer/dataset-explorer";
import { LayerOverview } from "@/features/explorer/layer-overview";
import { PresetExplorer } from "@/features/explorer/preset-explorer";
import { RegionalAvailability } from "@/features/explorer/regional-availability";

export default function ExplorePage() {
  return (
    <div>
      <PageHeader
        eyebrow="Metadata catalog"
        title="Explore"
        icon={<Compass className="h-7 w-7 text-brand" />}
        description="Everything the platform can serve — layers, datasets, presets, and regional availability — read live from the /meta/* APIs. This is the single source of truth the planner and API clients use."
      />

      <Tabs defaultValue="datasets">
        <TabsList>
          <TabsTrigger value="datasets">
            <Database className="h-3.5 w-3.5" /> Datasets
          </TabsTrigger>
          <TabsTrigger value="presets">
            <Boxes className="h-3.5 w-3.5" /> Presets
          </TabsTrigger>
          <TabsTrigger value="layers">
            <Layers className="h-3.5 w-3.5" /> Layers
          </TabsTrigger>
          <TabsTrigger value="regional">
            <MapPinned className="h-3.5 w-3.5" /> Regional availability
          </TabsTrigger>
        </TabsList>

        <TabsContent value="datasets">
          <DatasetExplorer />
        </TabsContent>
        <TabsContent value="presets">
          <PresetExplorer />
        </TabsContent>
        <TabsContent value="layers">
          <LayerOverview />
        </TabsContent>
        <TabsContent value="regional">
          <RegionalAvailability />
        </TabsContent>
      </Tabs>
    </div>
  );
}
