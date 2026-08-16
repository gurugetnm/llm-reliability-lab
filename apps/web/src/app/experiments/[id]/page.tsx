"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { History, Play } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { api, ApiError, type Experiment } from "@/lib/api";

function ReviewRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-4 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [experiment, setExperiment] = React.useState<Experiment | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [starting, setStarting] = React.useState(false);

  const load = React.useCallback(() => {
    api
      .getExperiment(id)
      .then((data) => {
        setExperiment(data);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load experiment"));
  }, [id]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleRun() {
    if (!experiment) return;
    setStarting(true);
    try {
      const run = await api.startRun(experiment.id);
      toast.success("Run started");
      router.push(`/experiments/${experiment.id}/runs/${run.id}`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="Experiment" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t load this experiment</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </>
    );
  }

  if (!experiment) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  const canRun = experiment.dataset.item_count > 0;

  return (
    <>
      <PageHeader
        title={experiment.name}
        description={experiment.description || "No description"}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              nativeButton={false}
              render={<Link href={`/experiments/${experiment.id}/runs`} />}
            >
              <History className="size-3.5" />
              View Runs
            </Button>
            <Button size="sm" disabled={!canRun || starting} onClick={handleRun}>
              <Play className="size-3.5" />
              {starting ? "Starting…" : "Run Experiment"}
            </Button>
          </div>
        }
      />

      {!canRun ? (
        <Alert className="mb-6">
          <AlertTitle>This dataset has no items</AlertTitle>
          <AlertDescription>
            Add items to &quot;{experiment.dataset.name}&quot; before running this experiment.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Configuration review</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border">
            <ReviewRow label="Dataset">
              <Link
                href={`/datasets/${experiment.dataset.id}`}
                className="hover:underline"
              >
                {experiment.dataset.name}
              </Link>{" "}
              <span className="text-muted-foreground">
                ({experiment.dataset.item_count} items)
              </span>
            </ReviewRow>
            <ReviewRow label="Model">
              <span className="font-mono text-xs">{experiment.model}</span>
            </ReviewRow>
            <ReviewRow label="Temperature">
              {experiment.generation_config.temperature}
            </ReviewRow>
            <ReviewRow label="Max Tokens">
              {experiment.generation_config.max_tokens ?? "Model default"}
            </ReviewRow>
            {experiment.system_prompt ? (
              <ReviewRow label="System Prompt">
                <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                  {experiment.system_prompt}
                </pre>
              </ReviewRow>
            ) : null}
            <ReviewRow label="User Prompt">
              <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
                {experiment.user_prompt_template}
              </pre>
            </ReviewRow>
            {experiment.structured_output_config ? (
              <ReviewRow label="Structured Output">
                <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                  {JSON.stringify(experiment.structured_output_config.schema, null, 2)}
                </pre>
              </ReviewRow>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Latest run</CardTitle>
          </CardHeader>
          <CardContent>
            {experiment.latest_run ? (
              <div className="space-y-3">
                <RunStatusBadge status={experiment.latest_run.status} />
                <dl className="space-y-1.5 text-xs text-muted-foreground">
                  <div className="flex justify-between">
                    <dt>Progress</dt>
                    <dd>
                      {experiment.latest_run.completed_items}/{experiment.latest_run.total_items}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Successful</dt>
                    <dd>{experiment.latest_run.successful_items}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Failed</dt>
                    <dd>{experiment.latest_run.failed_items}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Started</dt>
                    <dd>{formatDistanceToNow(experiment.latest_run.created_at)}</dd>
                  </div>
                </dl>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  nativeButton={false}
                  render={
                    <Link
                      href={`/experiments/${experiment.id}/runs/${experiment.latest_run.id}`}
                    />
                  }
                >
                  View Run
                </Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                This experiment hasn&apos;t been run yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
