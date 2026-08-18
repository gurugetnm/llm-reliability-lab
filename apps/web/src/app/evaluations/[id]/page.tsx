"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Ban, GitCompare, ListChecks } from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { EvaluationResultDetailSheet } from "@/components/evaluations/evaluation-result-detail-sheet";
import { EvaluationStatusBadge } from "@/components/evaluations/evaluation-status-badge";
import { PageHeader } from "@/components/page-header";
import { StatTile } from "@/components/stat-tile";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { streamEvaluationEvents } from "@/lib/evaluations/events";
import { formatDistanceToNow } from "@/lib/format";
import {
  api,
  ApiError,
  type EvaluationMetrics,
  type EvaluationResult,
  type EvaluationRun,
} from "@/lib/api";

const PAGE_SIZE = 25;
const ACTIVE_STATUSES = new Set(["pending", "running"]);

function truncate(text: string | null, max = 100): string {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export default function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();

  const [evaluation, setEvaluation] = React.useState<EvaluationRun | null>(null);
  const [metrics, setMetrics] = React.useState<EvaluationMetrics | null>(null);
  const [results, setResults] = React.useState<EvaluationResult[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<EvaluationResult | null>(null);
  const [cancelling, setCancelling] = React.useState(false);

  const loadResults = React.useCallback(() => {
    api
      .listEvaluationResults(id, 1, PAGE_SIZE)
      .then((page) => {
        setResults(page.items);
        setTotal(page.total);
      })
      .catch(() => {
        /* transient — the next poll/event will retry */
      });
  }, [id]);

  const loadMetrics = React.useCallback(() => {
    api
      .getEvaluationMetrics(id)
      .then(setMetrics)
      .catch(() => {});
  }, [id]);

  React.useEffect(() => {
    api
      .getEvaluation(id)
      .then((data) => {
        setEvaluation(data);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load evaluation"));
    loadResults();
    loadMetrics();
  }, [id, loadResults, loadMetrics]);

  React.useEffect(() => {
    if (!evaluation || !ACTIVE_STATUSES.has(evaluation.status)) return;

    const controller = new AbortController();
    (async () => {
      for await (const event of streamEvaluationEvents(id, controller.signal)) {
        if (
          event.type === "evaluation_started" ||
          event.type === "evaluation_progress" ||
          event.type === "evaluation_completed" ||
          event.type === "evaluation_cancelled"
        ) {
          setEvaluation((prev) =>
            prev
              ? {
                  ...prev,
                  status: event.data.status as EvaluationRun["status"],
                  total_items: event.data.total_items,
                  completed_items: event.data.completed_items,
                  successful_items: event.data.successful_items,
                  failed_items: event.data.failed_items,
                }
              : prev,
          );
          if (event.type === "evaluation_completed" || event.type === "evaluation_cancelled") {
            loadMetrics();
          }
        }
        if (event.type === "evaluation_item_completed" || event.type === "evaluation_item_failed") {
          loadResults();
        }
      }
    })();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, evaluation?.status === "pending" || evaluation?.status === "running"]);

  async function handleCancel() {
    setCancelling(true);
    try {
      await api.cancelEvaluation(id);
      toast.success("Cancellation requested");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to cancel evaluation");
    } finally {
      setCancelling(false);
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="Evaluation" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t load this evaluation</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </>
    );
  }

  if (!evaluation) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="mb-4 h-24 rounded-lg" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  const progressPct =
    evaluation.total_items > 0 ? (evaluation.completed_items / evaluation.total_items) * 100 : 0;
  const isActive = ACTIVE_STATUSES.has(evaluation.status);

  return (
    <>
      <PageHeader
        title={evaluation.name}
        description={`${evaluation.evaluator_type}:${evaluation.evaluator_version} · run ${evaluation.run_id.slice(0, 8)}`}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              nativeButton={false}
              render={<Link href={`/evaluations/compare?baseline=${evaluation.id}`} />}
            >
              <GitCompare className="size-3.5" />
              Compare
            </Button>
            {isActive ? (
              <Button variant="outline" size="sm" disabled={cancelling} onClick={handleCancel}>
                <Ban className="size-3.5" />
                {evaluation.cancel_requested || cancelling ? "Cancelling…" : "Cancel"}
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="mb-6 rounded-lg border border-border p-4">
        <div className="mb-3 flex flex-wrap items-center gap-4">
          <EvaluationStatusBadge status={evaluation.status} />
          <span className="text-sm tabular-nums">
            {evaluation.completed_items} / {evaluation.total_items} evaluated
          </span>
          <span className="text-sm text-emerald-600 dark:text-emerald-400">
            {evaluation.successful_items} successful
          </span>
          <span className="text-sm text-destructive">{evaluation.failed_items} failed</span>
          <span className="basis-full text-xs text-muted-foreground sm:basis-auto sm:ml-auto">
            Started {evaluation.started_at ? formatDistanceToNow(evaluation.started_at) : "not yet"}
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {metrics ? (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Pass rate" value={metrics.pass_rate === null ? "—" : `${Math.round(metrics.pass_rate * 100)}%`} />
          <StatTile label="Mean score" value={metrics.mean_score === null ? "—" : metrics.mean_score.toFixed(3)} />
          <StatTile label="Median score" value={metrics.median_score === null ? "—" : metrics.median_score.toFixed(3)} />
          <StatTile label="Evaluated" value={`${metrics.evaluated} / ${metrics.total}`} />
        </div>
      ) : null}

      {results === null ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : results.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="No results yet"
          description={
            isActive ? "Results will appear here as items are evaluated." : "This evaluation produced no results."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Input</th>
                  <th className="px-3 py-2 text-left font-medium">Actual Output</th>
                  <th className="px-3 py-2 text-right font-medium">Score</th>
                  <th className="px-3 py-2 text-right font-medium">Passed</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {results.map((result) => (
                  <tr
                    key={result.id}
                    className="cursor-pointer hover:bg-muted/30"
                    onClick={() => setSelected(result)}
                  >
                    <td className="max-w-xs px-3 py-2 font-mono text-xs">
                      {truncate(
                        typeof result.input === "string" ? result.input : JSON.stringify(result.input),
                      )}
                    </td>
                    <td className="max-w-xs px-3 py-2 font-mono text-xs text-muted-foreground">
                      {result.status === "failed"
                        ? truncate(result.error_message, 80)
                        : truncate(result.actual_output ?? JSON.stringify(result.actual_structured_output))}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {result.score === null ? "—" : result.score.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {result.passed === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : result.passed ? (
                        <span className="text-emerald-600 dark:text-emerald-400">Yes</span>
                      ) : (
                        <span className="text-destructive">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          result.status === "succeeded"
                            ? "text-emerald-600 dark:text-emerald-400"
                            : result.status === "failed"
                              ? "text-destructive"
                              : "text-muted-foreground"
                        }
                      >
                        {result.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {total > results.length ? (
            <div className="border-t border-border px-3 py-2 text-center text-xs text-muted-foreground">
              Showing the first {results.length} of {total} results
            </div>
          ) : null}
        </div>
      )}

      <EvaluationResultDetailSheet result={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </>
  );
}
