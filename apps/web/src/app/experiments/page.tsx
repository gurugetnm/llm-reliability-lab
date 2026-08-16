"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FlaskConical, History, Play } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { api, ApiError, type Experiment } from "@/lib/api";

export default function ExperimentsPage() {
  const router = useRouter();
  const [experiments, setExperiments] = React.useState<Experiment[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [runningId, setRunningId] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    api
      .listExperiments()
      .then((data) => {
        setExperiments(data);
        setError(null);
      })
      .catch((err) => {
        setExperiments([]);
        setError(err instanceof ApiError ? err.message : "Failed to load experiments");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleRun(experiment: Experiment) {
    setRunningId(experiment.id);
    try {
      const run = await api.startRun(experiment.id);
      toast.success("Run started");
      router.push(`/experiments/${experiment.id}/runs/${run.id}`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to start run");
    } finally {
      setRunningId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Experiments"
        description="Run and compare prompt, model, and generation configurations against a dataset."
        actions={
          <Button size="sm" render={<Link href="/experiments/new" />}>
            Create Experiment
          </Button>
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t reach the API</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {experiments === null ? (
        <div className="space-y-2">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
      ) : experiments.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="No experiments yet"
          description="Create an experiment to run a prompt and model configuration across a whole dataset."
          action={
            <Button size="sm" render={<Link href="/experiments/new" />}>
              Create Experiment
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Experiment</th>
                  <th className="px-3 py-2 text-left font-medium">Dataset</th>
                  <th className="px-3 py-2 text-left font-medium">Model</th>
                  <th className="px-3 py-2 text-left font-medium">Latest run</th>
                  <th className="px-3 py-2 text-left font-medium">Last run</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {experiments.map((experiment) => (
                  <tr key={experiment.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2.5">
                      <Link
                        href={`/experiments/${experiment.id}`}
                        className="font-medium hover:underline"
                      >
                        {experiment.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {experiment.dataset.name}{" "}
                      <span className="text-xs">({experiment.dataset.item_count} items)</span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">{experiment.model}</td>
                    <td className="px-3 py-2.5">
                      {experiment.latest_run ? (
                        <RunStatusBadge status={experiment.latest_run.status} />
                      ) : (
                        <span className="text-xs text-muted-foreground">No runs yet</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {experiment.latest_run
                        ? formatDistanceToNow(experiment.latest_run.created_at)
                        : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          render={<Link href={`/experiments/${experiment.id}/runs`} />}
                        >
                          <History className="size-3.5" />
                          Runs
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={runningId === experiment.id || experiment.dataset.item_count === 0}
                          onClick={() => handleRun(experiment)}
                        >
                          <Play className="size-3.5" />
                          {runningId === experiment.id ? "Starting…" : "Run"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
