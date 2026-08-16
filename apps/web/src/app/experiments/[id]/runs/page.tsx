"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, GitCompare, History } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { api, ApiError, type Experiment, type ExperimentRun } from "@/lib/api";

const PAGE_SIZE = 20;

function duration(run: ExperimentRun): string {
  if (!run.started_at) return "—";
  const end = run.completed_at ? new Date(run.completed_at) : new Date();
  const seconds = (end.getTime() - new Date(run.started_at).getTime()) / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

export default function ExperimentRunsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [experiment, setExperiment] = React.useState<Experiment | null>(null);
  const [runs, setRuns] = React.useState<ExperimentRun[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [error, setError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]);

  const load = React.useCallback(() => {
    setError(null);
    Promise.all([api.getExperiment(id), api.listRuns(id, page, PAGE_SIZE)])
      .then(([experimentResult, runsResult]) => {
        setExperiment(experimentResult);
        setRuns(runsResult.items);
        setTotal(runsResult.total);
      })
      .catch((err) => {
        setRuns([]);
        setError(err instanceof ApiError ? err.message : "Failed to load runs");
      });
  }, [id, page]);

  React.useEffect(() => {
    // `load` sets state from an async .then, not synchronously here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  function toggleSelected(runId: string) {
    setSelected((prev) => {
      if (prev.includes(runId)) return prev.filter((r) => r !== runId);
      if (prev.length >= 2) return [prev[1], runId];
      return [...prev, runId];
    });
  }

  function handleCompare() {
    if (selected.length !== 2) {
      toast.error("Select exactly two runs to compare");
      return;
    }
    router.push(`/experiments/${id}/runs/compare?a=${selected[0]}&b=${selected[1]}`);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (!experiment && !error) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={experiment ? `Runs — ${experiment.name}` : "Runs"}
        description="Every past execution of this experiment."
        actions={
          <Button variant="outline" size="sm" disabled={selected.length !== 2} onClick={handleCompare}>
            <GitCompare className="size-3.5" />
            Compare selected
          </Button>
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t load runs</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {runs === null ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : runs.length === 0 ? (
        <EmptyState
          icon={History}
          title="No runs yet"
          description="Run this experiment to see its history here."
          action={
            <Button size="sm" nativeButton={false} render={<Link href={`/experiments/${id}`} />}>
              Go to experiment
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="w-8 px-3 py-2" />
                  <th className="px-3 py-2 text-left font-medium">Run</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-left font-medium">Started</th>
                  <th className="px-3 py-2 text-left font-medium">Duration</th>
                  <th className="px-3 py-2 text-right font-medium">Items</th>
                  <th className="px-3 py-2 text-right font-medium">Successful</th>
                  <th className="px-3 py-2 text-right font-medium">Failed</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2.5">
                      <Checkbox
                        checked={selected.includes(run.id)}
                        onCheckedChange={() => toggleSelected(run.id)}
                        aria-label={`Select run ${run.id}`}
                      />
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">
                      {run.id.slice(0, 8)}
                    </td>
                    <td className="px-3 py-2.5">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {run.started_at ? formatDistanceToNow(run.started_at) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {duration(run)}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{run.total_items}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-emerald-600 dark:text-emerald-400">
                      {run.successful_items}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-destructive">
                      {run.failed_items}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        nativeButton={false}
                        render={<Link href={`/experiments/${id}/runs/${run.id}`} />}
                      >
                        View Run
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-muted-foreground">
              <span>
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </>
  );
}
