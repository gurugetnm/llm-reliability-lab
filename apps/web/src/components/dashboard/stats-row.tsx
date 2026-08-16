"use client";

import * as React from "react";

import { StatTile } from "@/components/stat-tile";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { llm } from "@/lib/llm/client";

export function StatsRow({ refreshKey }: { refreshKey: number }) {
  const [projectCount, setProjectCount] = React.useState<number | null>(null);
  const [modelCount, setModelCount] = React.useState<number | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .listProjects()
      .then((projects) => {
        if (!cancelled) setProjectCount(projects.length);
      })
      .catch(() => {
        if (!cancelled) setProjectCount(0);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  React.useEffect(() => {
    let cancelled = false;
    llm
      .listModels()
      .then((models) => {
        if (!cancelled) setModelCount(models.length);
      })
      .catch(() => {
        // Ollama being unreachable shouldn't block the rest of the
        // dashboard — the Models page itself explains why.
        if (!cancelled) setModelCount(0);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {projectCount === null ? (
        <Skeleton className="h-[74px] rounded-lg" />
      ) : (
        <StatTile label="Projects" value={projectCount} />
      )}
      <StatTile label="Experiments" value={0} />
      <StatTile label="Evaluation Runs" value={0} />
      {modelCount === null ? (
        <Skeleton className="h-[74px] rounded-lg" />
      ) : (
        <StatTile label="Models" value={modelCount} />
      )}
    </div>
  );
}
