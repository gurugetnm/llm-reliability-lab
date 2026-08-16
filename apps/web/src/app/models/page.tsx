"use client";

import * as React from "react";
import { AlertTriangle, Cpu, RefreshCw } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { llm } from "@/lib/llm/client";
import type { ModelSummary } from "@/lib/llm/types";

type LoadState = "loading" | "ready" | "unavailable";

function formatSize(bytes: number | null): string | null {
  if (!bytes) return null;
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(0)} MB`;
}

function formatModifiedAt(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ModelsPage() {
  const [models, setModels] = React.useState<ModelSummary[]>([]);
  const [state, setState] = React.useState<LoadState>("loading");
  const [error, setError] = React.useState<string | null>(null);

  // No synchronous setState here (only inside the .then/.catch below) so
  // this is safe to call directly from the mount effect.
  const fetchModels = React.useCallback(() => {
    llm
      .listModels()
      .then((result) => {
        setModels(result);
        setState("ready");
      })
      .catch((err) => {
        setModels([]);
        setState("unavailable");
        setError(err instanceof Error ? err.message : "Could not reach the API");
      });
  }, []);

  // Distinct from fetchModels: resets to the loading state synchronously,
  // which only makes sense from a user-triggered refresh, not on mount
  // (the initial state is already "loading").
  const refresh = React.useCallback(() => {
    setState("loading");
    setError(null);
    fetchModels();
  }, [fetchModels]);

  React.useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  return (
    <>
      <PageHeader
        title="Models"
        description="Local and remote LLM providers available to your experiments."
        actions={
          <Button variant="outline" size="sm" onClick={refresh} disabled={state === "loading"}>
            <RefreshCw className={state === "loading" ? "size-3.5 animate-spin" : "size-3.5"} />
            Refresh
          </Button>
        }
      />

      {state === "loading" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-32 rounded-lg" />
        </div>
      ) : state === "unavailable" ? (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Ollama is unreachable</AlertTitle>
          <AlertDescription>
            <p>{error ?? "Could not reach Ollama."}</p>
            <p className="mt-1">
              Make sure Ollama is running and{" "}
              <code className="font-mono">OLLAMA_BASE_URL</code> is configured correctly, then
              refresh.
            </p>
          </AlertDescription>
        </Alert>
      ) : models.length === 0 ? (
        <EmptyState
          icon={Cpu}
          title="No models installed"
          description={
            'Ollama is running but has no models pulled yet. Run "ollama pull llama3.1" (or any model) on the host, then refresh.'
          }
          action={
            <Button variant="outline" size="sm" onClick={refresh}>
              <RefreshCw className="size-3.5" />
              Refresh
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {models.map((model) => {
            const size = formatSize(model.size_bytes);
            const modified = formatModifiedAt(model.modified_at);
            return (
              <Card key={model.name}>
                <CardHeader>
                  <CardTitle className="truncate font-mono text-sm font-medium">
                    {model.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary" className="font-normal">
                      {model.provider}
                    </Badge>
                    {model.parameter_size ? (
                      <Badge variant="secondary" className="font-normal">
                        {model.parameter_size}
                      </Badge>
                    ) : null}
                    {model.quantization ? (
                      <Badge variant="secondary" className="font-normal">
                        {model.quantization}
                      </Badge>
                    ) : null}
                    {size ? (
                      <Badge variant="secondary" className="font-normal">
                        {size}
                      </Badge>
                    ) : null}
                  </div>
                  <dl className="space-y-1 text-xs text-muted-foreground">
                    {model.family ? (
                      <div className="flex justify-between gap-2">
                        <dt>Family</dt>
                        <dd className="text-foreground">{model.family}</dd>
                      </div>
                    ) : null}
                    {modified ? (
                      <div className="flex justify-between gap-2">
                        <dt>Modified</dt>
                        <dd className="text-foreground">{modified}</dd>
                      </div>
                    ) : null}
                  </dl>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
