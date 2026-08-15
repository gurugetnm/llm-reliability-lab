"use client";

import * as React from "react";
import { FlaskConical } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatsRow } from "@/components/dashboard/stats-row";
import { EmptyState } from "@/components/empty-state";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);

  return (
    <>
      <PageHeader
        title="LLM Reliability Lab"
        description="Experiment, evaluate, and understand your AI systems."
        actions={<CreateProjectDialog onCreated={() => setRefreshKey((key) => key + 1)} />}
      />

      <StatsRow refreshKey={refreshKey} />

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Recent Experiments</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={FlaskConical}
            title="No experiments yet"
            description="Experiments let you compare prompts, models, and RAG configurations side by side. Start by creating a project."
          />
        </CardContent>
      </Card>
    </>
  );
}
