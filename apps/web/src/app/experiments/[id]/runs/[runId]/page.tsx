"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { Ban, ListChecks } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { RunItemDetailSheet } from "@/components/experiments/run-item-detail-sheet";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { streamRunEvents } from "@/lib/runs/events";
import { api, ApiError, type Experiment, type ExperimentRun, type RunItem } from "@/lib/api";

const PAGE_SIZE = 25;
const ACTIVE_STATUSES = new Set(["pending", "running"]);

function truncate(text: string | null, max = 100): string {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export default function RunDetailPage() {
  const { id, runId } = useParams<{ id: string; runId: string }>();

  const [experiment, setExperiment] = React.useState<Experiment | null>(null);
  const [run, setRun] = React.useState<ExperimentRun | null>(null);
  const [items, setItems] = React.useState<RunItem[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedItem, setSelectedItem] = React.useState<RunItem | null>(null);
  const [cancelling, setCancelling] = React.useState(false);

  const loadItems = React.useCallback(() => {
    api
      .listRunItems(runId, 1, PAGE_SIZE)
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch(() => {
        /* transient — the next poll/event will retry */
      });
  }, [runId]);

  React.useEffect(() => {
    api
      .getExperiment(id)
      .then(setExperiment)
      .catch(() => {});
    api
      .getRun(runId)
      .then((data) => {
        setRun(data);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load run"));
    loadItems();
  }, [id, runId, loadItems]);

  React.useEffect(() => {
    if (!run || !ACTIVE_STATUSES.has(run.status)) return;

    const controller = new AbortController();
    (async () => {
      for await (const event of streamRunEvents(runId, controller.signal)) {
        if (
          event.type === "run_started" ||
          event.type === "run_progress" ||
          event.type === "run_completed" ||
          event.type === "run_cancelled"
        ) {
          setRun((prev) =>
            prev
              ? {
                  ...prev,
                  status: event.data.status as ExperimentRun["status"],
                  total_items: event.data.total_items,
                  completed_items: event.data.completed_items,
                  successful_items: event.data.successful_items,
                  failed_items: event.data.failed_items,
                }
              : prev,
          );
        }
        if (event.type === "run_item_completed" || event.type === "run_item_failed") {
          loadItems();
        }
      }
    })();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, run?.status === "pending" || run?.status === "running"]);

  async function handleCancel() {
    setCancelling(true);
    try {
      await api.cancelRun(runId);
      toast.success("Cancellation requested");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="Run" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t load this run</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </>
    );
  }

  if (!run) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="mb-4 h-24 rounded-lg" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  const progressPct = run.total_items > 0 ? (run.completed_items / run.total_items) * 100 : 0;
  const isActive = ACTIVE_STATUSES.has(run.status);

  return (
    <>
      <PageHeader
        title={`Run ${run.id.slice(0, 8)}`}
        description={experiment ? `${experiment.name} · ${run.model}` : run.model}
        actions={
          isActive ? (
            <Button variant="outline" size="sm" disabled={cancelling} onClick={handleCancel}>
              <Ban className="size-3.5" />
              {run.cancel_requested ? "Cancelling…" : cancelling ? "Cancelling…" : "Cancel Run"}
            </Button>
          ) : undefined
        }
      />

      <div className="mb-6 rounded-lg border border-border p-4">
        <div className="mb-3 flex flex-wrap items-center gap-4">
          <RunStatusBadge status={run.status} />
          <span className="text-sm tabular-nums">
            {run.completed_items} / {run.total_items} items
          </span>
          <span className="text-sm text-emerald-600 dark:text-emerald-400">
            {run.successful_items} successful
          </span>
          <span className="text-sm text-destructive">{run.failed_items} failed</span>
          <span className="ml-auto text-xs text-muted-foreground">
            Started {run.started_at ? formatDistanceToNow(run.started_at) : "not yet"}
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {items === null ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="No items yet"
          description={
            isActive ? "Generations will appear here as they complete." : "This run produced no items."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Prompt</th>
                  <th className="px-3 py-2 text-left font-medium">Response</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-right font-medium">Latency</th>
                  <th className="px-3 py-2 text-right font-medium">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/30"
                    onClick={() => setSelectedItem(item)}
                  >
                    <td className="max-w-xs px-3 py-2 font-mono text-xs">
                      {truncate(item.user_prompt)}
                    </td>
                    <td className="max-w-xs px-3 py-2 font-mono text-xs text-muted-foreground">
                      {item.status === "failed"
                        ? truncate(item.error_message, 80)
                        : truncate(item.response ?? JSON.stringify(item.structured_output))}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          item.status === "succeeded"
                            ? "text-emerald-600 dark:text-emerald-400"
                            : item.status === "failed"
                              ? "text-destructive"
                              : "text-muted-foreground"
                        }
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs text-muted-foreground">
                      {item.latency_ms ? `${Math.round(item.latency_ms)}ms` : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs text-muted-foreground">
                      {item.total_tokens ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {total > items.length ? (
            <div className="border-t border-border px-3 py-2 text-center text-xs text-muted-foreground">
              Showing the first {items.length} of {total} items
            </div>
          ) : null}
        </div>
      )}

      <RunItemDetailSheet item={selectedItem} onOpenChange={(open) => !open && setSelectedItem(null)} />
    </>
  );
}
