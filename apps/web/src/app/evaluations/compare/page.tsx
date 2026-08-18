"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { EvaluationStatusBadge } from "@/components/evaluations/evaluation-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/stat-tile";
import { api, ApiError, type EvaluationComparison, type EvaluationRun } from "@/lib/api";
import { cn } from "@/lib/utils";

function formatScore(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

function formatPct(value: number | null): string {
  if (value === null) return "—";
  const pct = value * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function EvaluationPicker({
  label,
  evaluations,
  value,
  onChange,
}: {
  label: string;
  evaluations: EvaluationRun[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Select value={value || undefined} onValueChange={(v) => v && onChange(v)}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select an evaluation" />
        </SelectTrigger>
        <SelectContent>
          {evaluations.map((evaluation) => (
            <SelectItem key={evaluation.id} value={evaluation.id}>
              {evaluation.name} ({evaluation.evaluator_type})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function CompareEvaluationsPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
      <CompareEvaluationsContent />
    </React.Suspense>
  );
}

/** Split out because `useSearchParams()` requires a Suspense boundary
 * around it for static prerendering — `/evaluations/compare` (unlike
 * `/experiments/[id]/runs/compare`) has no dynamic route segment, so
 * Next.js attempts to prerender it at build time. */
function CompareEvaluationsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const baselineId = searchParams.get("baseline") ?? "";
  const candidateId = searchParams.get("candidate") ?? "";

  const [evaluations, setEvaluations] = React.useState<EvaluationRun[]>([]);
  const [pickerBaseline, setPickerBaseline] = React.useState(baselineId);
  const [pickerCandidate, setPickerCandidate] = React.useState(candidateId);
  const [comparison, setComparison] = React.useState<EvaluationComparison | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .listEvaluations(undefined, 1, 100)
      .then((page) => setEvaluations(page.items))
      .catch(() => setEvaluations([]));
  }, []);

  React.useEffect(() => {
    if (!baselineId || !candidateId) {
      // A startup precondition (missing query params), not state derived
      // from an async call.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setComparison(null);
      return;
    }
    setError(null);
    api
      .compareEvaluations(baselineId, candidateId)
      .then(setComparison)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to compare evaluations"));
  }, [baselineId, candidateId]);

  function handleCompare() {
    if (!pickerBaseline || !pickerCandidate) return;
    router.push(`/evaluations/compare?baseline=${pickerBaseline}&candidate=${pickerCandidate}`);
  }

  return (
    <>
      <PageHeader
        title="Compare Evaluations"
        description="Baseline vs. candidate scores, using the same evaluator, with regression detection."
      />

      <Card className="mb-6">
        <CardContent className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <EvaluationPicker
            label="Baseline"
            evaluations={evaluations}
            value={pickerBaseline}
            onChange={setPickerBaseline}
          />
          <EvaluationPicker
            label="Candidate"
            evaluations={evaluations}
            value={pickerCandidate}
            onChange={setPickerCandidate}
          />
          <Button onClick={handleCompare} disabled={!pickerBaseline || !pickerCandidate}>
            Compare
          </Button>
        </CardContent>
      </Card>

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t compare these evaluations</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!baselineId || !candidateId ? (
        <p className="text-sm text-muted-foreground">
          Select a baseline and a candidate evaluation above to compare them.
        </p>
      ) : !comparison && !error ? (
        <Skeleton className="h-64 rounded-lg" />
      ) : comparison ? (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-border p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Baseline
                </p>
                <EvaluationStatusBadge status={comparison.baseline.status} />
              </div>
              <Link href={`/evaluations/${comparison.baseline.id}`} className="font-medium hover:underline">
                {comparison.baseline.name}
              </Link>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {formatScore(comparison.baseline_metrics.mean_score)}
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Candidate
                </p>
                <EvaluationStatusBadge status={comparison.candidate.status} />
              </div>
              <Link href={`/evaluations/${comparison.candidate.id}`} className="font-medium hover:underline">
                {comparison.candidate.name}
              </Link>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {formatScore(comparison.candidate_metrics.mean_score)}
              </p>
            </div>
          </div>

          {comparison.regression ? (
            <Alert
              className={cn(
                "mb-6",
                comparison.regression.regression_detected
                  ? "border-destructive/40 bg-destructive/5"
                  : "border-emerald-500/40 bg-emerald-500/5",
              )}
            >
              {comparison.regression.regression_detected ? (
                <AlertTriangle className="size-4 text-destructive" />
              ) : (
                <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
              )}
              <AlertTitle>
                {comparison.regression.regression_detected ? "Regression detected" : "No regression detected"}
              </AlertTitle>
              <AlertDescription>
                Change: {formatPct(comparison.regression.relative_difference)} (
                {comparison.regression.difference >= 0 ? "+" : ""}
                {comparison.regression.difference.toFixed(3)} absolute, threshold{" "}
                {comparison.regression.threshold.toFixed(3)}). This is a simple engineering
                comparison, not a statistical significance test.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert className="mb-6">
              <AlertTitle>Not enough data to compare</AlertTitle>
              <AlertDescription>
                At least one of these evaluations has no scored results yet.
              </AlertDescription>
            </Alert>
          )}

          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Baseline pass rate" value={comparison.baseline_metrics.pass_rate === null ? "—" : `${Math.round(comparison.baseline_metrics.pass_rate * 100)}%`} />
            <StatTile label="Candidate pass rate" value={comparison.candidate_metrics.pass_rate === null ? "—" : `${Math.round(comparison.candidate_metrics.pass_rate * 100)}%`} />
            <StatTile label="Baseline evaluated" value={`${comparison.baseline_metrics.evaluated} / ${comparison.baseline_metrics.total}`} />
            <StatTile label="Candidate evaluated" value={`${comparison.candidate_metrics.evaluated} / ${comparison.candidate_metrics.total}`} />
          </div>

          {comparison.items.length > 0 ? (
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Dataset item</th>
                      <th className="px-3 py-2 text-right font-medium">Baseline</th>
                      <th className="px-3 py-2 text-right font-medium">Candidate</th>
                      <th className="px-3 py-2 text-right font-medium">Δ</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {comparison.items.map((item, index) => (
                      <tr key={item.dataset_item_id ?? index} className="hover:bg-muted/30">
                        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                          {item.dataset_item_id ? item.dataset_item_id.slice(0, 8) : "—"}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatScore(item.baseline_score)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatScore(item.candidate_score)}
                        </td>
                        <td
                          className={cn(
                            "px-3 py-2 text-right tabular-nums font-medium",
                            item.difference === null
                              ? "text-muted-foreground"
                              : item.difference > 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : item.difference < 0
                                  ? "text-destructive"
                                  : "text-muted-foreground",
                          )}
                        >
                          {item.difference === null
                            ? "—"
                            : `${item.difference >= 0 ? "+" : ""}${item.difference.toFixed(3)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
