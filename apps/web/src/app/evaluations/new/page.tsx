"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { EvaluatorConfigFields } from "@/components/evaluations/evaluator-config-fields";
import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  api,
  ApiError,
  type EvaluatorInfo,
  type Experiment,
  type ExperimentRun,
} from "@/lib/api";

const TERMINAL_STATUSES = new Set([
  "completed",
  "completed_with_errors",
  "failed",
  "cancelled",
]);

export default function NewEvaluationPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-96 rounded-lg" />}>
      <NewEvaluationContent />
    </React.Suspense>
  );
}

/** Split out because `useSearchParams()` requires a Suspense boundary
 * for static prerendering of a route with no dynamic segment — see the
 * same note in evaluations/compare/page.tsx. */
function NewEvaluationContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefilledRunId = searchParams.get("runId");

  const [evaluators, setEvaluators] = React.useState<EvaluatorInfo[] | null>(null);
  const [experiments, setExperiments] = React.useState<Experiment[] | null>(null);
  const [experimentId, setExperimentId] = React.useState("");
  const [runs, setRuns] = React.useState<ExperimentRun[] | null>(null);
  const [runId, setRunId] = React.useState(prefilledRunId ?? "");
  const [prefilledRun, setPrefilledRun] = React.useState<ExperimentRun | null>(null);

  const [evaluatorType, setEvaluatorType] = React.useState("");
  const [config, setConfig] = React.useState<Record<string, unknown>>({});
  const [name, setName] = React.useState("");
  const [nameTouched, setNameTouched] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.listEvaluators().then(setEvaluators).catch(() => setEvaluators([]));
    if (!prefilledRunId) {
      api.listExperiments().then(setExperiments).catch(() => setExperiments([]));
    } else {
      api
        .getRun(prefilledRunId)
        .then(setPrefilledRun)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load run"));
    }
  }, [prefilledRunId]);

  React.useEffect(() => {
    if (prefilledRunId || !experimentId) return;
    api
      .listRuns(experimentId, 1, 50)
      .then((page) => setRuns(page.items))
      .catch(() => setRuns([]));
  }, [experimentId, prefilledRunId]);

  React.useEffect(() => {
    if (experiments && experiments.length > 0 && !experimentId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setExperimentId(experiments[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [experiments]);

  React.useEffect(() => {
    if (evaluators && evaluators.length > 0 && !evaluatorType) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEvaluatorType(evaluators[0].name);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evaluators]);

  React.useEffect(() => {
    if (!nameTouched && evaluatorType) {
      // Derived default, not independent state the user asked for.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setName(`${evaluatorType.replace(/_/g, " ")} evaluation`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evaluatorType]);

  const selectedEvaluator = evaluators?.find((e) => e.name === evaluatorType) ?? null;
  const terminalRuns = (runs ?? []).filter((r) => TERMINAL_STATUSES.has(r.status));
  const effectiveRunId = prefilledRunId ?? runId;
  const configValid =
    evaluatorType !== "llm_judge" ||
    (typeof config.judge_model === "string" && config.judge_model.trim().length > 0);
  const configValidContains =
    evaluatorType !== "contains" ||
    (Array.isArray(config.required_terms) && config.required_terms.length > 0);
  const canSubmit =
    Boolean(effectiveRunId) &&
    Boolean(evaluatorType) &&
    Boolean(name.trim()) &&
    configValid &&
    configValidContains;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    try {
      const evaluation = await api.createEvaluation({
        run_id: effectiveRunId,
        name: name.trim(),
        evaluator_type: evaluatorType,
        configuration: config,
      });
      toast.success(`Evaluation "${evaluation.name}" started`);
      router.push(`/evaluations/${evaluation.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to start evaluation");
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="New Evaluation" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t load this run</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="New Evaluation"
        description="Score a completed experiment run's outputs against your dataset."
      />

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-4">
            <h2 className="text-sm font-medium">1. Experiment run</h2>

            {prefilledRunId ? (
              prefilledRun ? (
                <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                  <div>
                    <p className="font-mono text-xs text-muted-foreground">
                      {prefilledRun.id.slice(0, 8)}
                    </p>
                    <p>{prefilledRun.model}</p>
                  </div>
                  <RunStatusBadge status={prefilledRun.status} />
                </div>
              ) : (
                <Skeleton className="h-12 rounded-md" />
              )
            ) : (
              <>
                <div className="grid gap-1.5">
                  <Label htmlFor="eval-experiment">Experiment</Label>
                  {experiments === null ? (
                    <p className="text-xs text-muted-foreground">Loading experiments…</p>
                  ) : experiments.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No experiments yet — create and run one first.
                    </p>
                  ) : (
                    <Select
                      value={experimentId || undefined}
                      onValueChange={(v) => {
                        if (!v) return;
                        setExperimentId(v);
                        setRunId("");
                      }}
                    >
                      <SelectTrigger id="eval-experiment" className="w-full">
                        <SelectValue placeholder="Select an experiment" />
                      </SelectTrigger>
                      <SelectContent>
                        {experiments.map((experiment) => (
                          <SelectItem key={experiment.id} value={experiment.id}>
                            {experiment.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="eval-run">Run</Label>
                  {!experimentId ? null : runs === null ? (
                    <p className="text-xs text-muted-foreground">Loading runs…</p>
                  ) : terminalRuns.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No finished runs yet for this experiment — a run must complete before it
                      can be evaluated.
                    </p>
                  ) : (
                    <Select value={runId || undefined} onValueChange={(v) => v && setRunId(v)}>
                      <SelectTrigger id="eval-run" className="w-full">
                        <SelectValue placeholder="Select a finished run" />
                      </SelectTrigger>
                      <SelectContent>
                        {terminalRuns.map((run) => (
                          <SelectItem key={run.id} value={run.id}>
                            {run.id.slice(0, 8)} — {run.model} ({run.status})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </>
            )}

            <h2 className="pt-2 text-sm font-medium">2. Evaluator</h2>
            <div className="grid gap-1.5">
              <Label htmlFor="eval-type">Evaluator type</Label>
              {evaluators === null ? (
                <p className="text-xs text-muted-foreground">Loading evaluators…</p>
              ) : (
                <Select value={evaluatorType || undefined} onValueChange={(v) => v && setEvaluatorType(v)}>
                  <SelectTrigger id="eval-type" className="w-full">
                    <SelectValue placeholder="Select an evaluator" />
                  </SelectTrigger>
                  <SelectContent>
                    {evaluators.map((e) => (
                      <SelectItem key={e.name} value={e.name}>
                        {e.name.replace(/_/g, " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedEvaluator ? (
                <p className="text-xs text-muted-foreground">{selectedEvaluator.description}</p>
              ) : null}
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="eval-name">Name</Label>
              <Input
                id="eval-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setNameTouched(true);
                }}
                required
              />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-4">
              <h2 className="text-sm font-medium">3. Configuration</h2>
              {evaluatorType ? (
                <EvaluatorConfigFields
                  evaluatorType={evaluatorType}
                  config={config}
                  onChange={setConfig}
                />
              ) : (
                <p className="text-xs text-muted-foreground">
                  Select an evaluator to configure it.
                </p>
              )}
            </CardContent>
          </Card>

          <Button type="submit" className="w-full" disabled={!canSubmit || submitting}>
            {submitting ? "Starting…" : "Start Evaluation"}
          </Button>
        </div>
      </form>
    </>
  );
}
