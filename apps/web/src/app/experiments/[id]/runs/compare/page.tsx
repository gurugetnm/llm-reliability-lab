"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { DiffText } from "@/components/experiments/diff-text";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type ExperimentRun, type RunItem } from "@/lib/api";
import { diffWords } from "@/lib/text-diff";

// Matches the backend's MAX_PAGE_SIZE (app/schemas/pagination.py) — the
// largest page_size the API will accept without a 422.
const MAX_ITEMS = 100;

interface PairedItem {
  key: string;
  a: RunItem | null;
  b: RunItem | null;
}

function pairItems(itemsA: RunItem[], itemsB: RunItem[]): PairedItem[] {
  const byDatasetItemB = new Map(itemsB.filter((i) => i.dataset_item_id).map((i) => [i.dataset_item_id!, i]));
  const paired: PairedItem[] = [];
  const usedB = new Set<string>();

  for (const itemA of itemsA) {
    const match = itemA.dataset_item_id ? byDatasetItemB.get(itemA.dataset_item_id) : undefined;
    paired.push({ key: itemA.id, a: itemA, b: match ?? null });
    if (match) usedB.add(match.id);
  }
  for (const itemB of itemsB) {
    if (!usedB.has(itemB.id)) paired.push({ key: itemB.id, a: null, b: itemB });
  }
  return paired;
}

function RunColumnHeader({ run }: { run: ExperimentRun }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-border pb-2">
      <div>
        <p className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 8)}</p>
        <p className="text-sm font-medium">{run.model}</p>
        <p className="text-xs text-muted-foreground">
          temperature {run.generation_config.temperature}
        </p>
      </div>
      <RunStatusBadge status={run.status} />
    </div>
  );
}

export default function CompareRunsPage() {
  const searchParams = useSearchParams();
  const runAId = searchParams.get("a");
  const runBId = searchParams.get("b");

  const [runA, setRunA] = React.useState<ExperimentRun | null>(null);
  const [runB, setRunB] = React.useState<ExperimentRun | null>(null);
  const [paired, setPaired] = React.useState<PairedItem[] | null>(null);
  const [index, setIndex] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!runAId || !runBId) {
      // Missing query params is a startup precondition, not a value
      // derived from other state — setting it here is the point.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("Two run ids are required to compare (?a=...&b=...)");
      return;
    }
    Promise.all([
      api.getRun(runAId),
      api.getRun(runBId),
      api.listRunItems(runAId, 1, MAX_ITEMS),
      api.listRunItems(runBId, 1, MAX_ITEMS),
    ])
      .then(([a, b, itemsA, itemsB]) => {
        setRunA(a);
        setRunB(b);
        setPaired(pairItems(itemsA.items, itemsB.items));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load runs"));
  }, [runAId, runBId]);

  if (error) {
    return (
      <>
        <PageHeader title="Compare Runs" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t compare these runs</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </>
    );
  }

  if (!runA || !runB || !paired) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  if (paired.length === 0) {
    return (
      <>
        <PageHeader title="Compare Runs" />
        <Alert>
          <AlertTitle>Nothing to compare</AlertTitle>
          <AlertDescription>Neither run produced any items yet.</AlertDescription>
        </Alert>
      </>
    );
  }

  const current = paired[Math.min(index, paired.length - 1)];
  const responseA = current.a?.response ?? (current.a?.structured_output ? JSON.stringify(current.a.structured_output, null, 2) : "");
  const responseB = current.b?.response ?? (current.b?.structured_output ? JSON.stringify(current.b.structured_output, null, 2) : "");
  const { left, right } = diffWords(responseA, responseB);

  return (
    <>
      <PageHeader
        title="Compare Runs"
        description="Response, latency, and tokens side by side — no scores or verdicts."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              disabled={index <= 0}
              onClick={() => setIndex((i) => i - 1)}
              aria-label="Previous item"
            >
              <ChevronLeft className="size-3.5" />
            </Button>
            <span className="text-xs tabular-nums text-muted-foreground">
              {index + 1} / {paired.length}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              disabled={index >= paired.length - 1}
              onClick={() => setIndex((i) => i + 1)}
              aria-label="Next item"
            >
              <ChevronRight className="size-3.5" />
            </Button>
          </div>
        }
      />

      <div className="mb-4 rounded-lg border border-border p-4">
        <h3 className="mb-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Dataset Item
        </h3>
        <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
          {current.a?.user_prompt ?? current.b?.user_prompt ?? "—"}
        </pre>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <RunColumnHeader run={runA} />
          {current.a ? (
            <>
              <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-muted/20 p-3 font-mono text-xs">
                <DiffText parts={left} />
              </pre>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>{current.a.latency_ms ? `${Math.round(current.a.latency_ms)}ms` : "—"}</span>
                <span>{current.a.total_tokens ?? "—"} tokens</span>
                <span>{current.a.status}</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No matching item in this run.</p>
          )}
        </div>

        <div className="space-y-2">
          <RunColumnHeader run={runB} />
          {current.b ? (
            <>
              <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-muted/20 p-3 font-mono text-xs">
                <DiffText parts={right} />
              </pre>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>{current.b.latency_ms ? `${Math.round(current.b.latency_ms)}ms` : "—"}</span>
                <span>{current.b.total_tokens ?? "—"} tokens</span>
                <span>{current.b.status}</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No matching item in this run.</p>
          )}
        </div>
      </div>
    </>
  );
}
