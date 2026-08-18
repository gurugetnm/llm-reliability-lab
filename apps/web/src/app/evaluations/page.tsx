"use client";

import * as React from "react";
import Link from "next/link";
import { CheckSquare } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { EvaluationStatusBadge } from "@/components/evaluations/evaluation-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { api, ApiError, type EvaluationMetrics, type EvaluationRun } from "@/lib/api";

function formatScore(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

function formatPassRate(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export default function EvaluationsPage() {
  const [evaluations, setEvaluations] = React.useState<EvaluationRun[] | null>(null);
  const [metrics, setMetrics] = React.useState<Record<string, EvaluationMetrics>>({});
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setError(null);
    api
      .listEvaluations(undefined, 1, 50)
      .then((page) => {
        setEvaluations(page.items);
        // A handful of parallel requests against a cheap aggregate
        // endpoint — reasonable for a local lab's evaluation list;
        // worth a dedicated list-with-metrics endpoint if this list
        // grows into the hundreds.
        Promise.all(
          page.items.map((e) =>
            api
              .getEvaluationMetrics(e.id)
              .then((m) => [e.id, m] as const)
              .catch(() => null),
          ),
        ).then((entries) => {
          setMetrics(Object.fromEntries(entries.filter((e) => e !== null)));
        });
      })
      .catch((err) => {
        setEvaluations([]);
        setError(err instanceof ApiError ? err.message : "Failed to load evaluations");
      });
  }, []);

  React.useEffect(() => {
    // `load` sets state from an async .then, not synchronously here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Evaluations"
        description="Score and compare experiment runs against your datasets."
        actions={
          <Button size="sm" nativeButton={false} render={<Link href="/evaluations/new" />}>
            New Evaluation
          </Button>
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t load evaluations</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {evaluations === null ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : evaluations.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title="No evaluation runs yet"
          description="Score a completed experiment run against exact-match, contains, semantic similarity, or LLM-as-judge evaluators, and detect regressions between runs."
          action={
            <Button size="sm" nativeButton={false} render={<Link href="/evaluations/new" />}>
              New Evaluation
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Evaluation</th>
                  <th className="px-3 py-2 text-left font-medium">Evaluator</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-right font-medium">Mean score</th>
                  <th className="px-3 py-2 text-right font-medium">Pass rate</th>
                  <th className="px-3 py-2 text-left font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {evaluations.map((evaluation) => (
                  <tr key={evaluation.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2.5">
                      <Link
                        href={`/evaluations/${evaluation.id}`}
                        className="font-medium hover:underline"
                      >
                        {evaluation.name}
                      </Link>
                      <p className="font-mono text-xs text-muted-foreground">
                        run {evaluation.run_id.slice(0, 8)}
                      </p>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">
                      {evaluation.evaluator_type}:{evaluation.evaluator_version}
                    </td>
                    <td className="px-3 py-2.5">
                      <EvaluationStatusBadge status={evaluation.status} />
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {formatScore(metrics[evaluation.id]?.mean_score ?? null)}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {formatPassRate(metrics[evaluation.id]?.pass_rate ?? null)}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {formatDistanceToNow(evaluation.created_at)}
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
