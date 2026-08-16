"use client";

import * as React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { llm } from "@/lib/llm/client";
import type { ModelSummary } from "@/lib/llm/types";
import { cn } from "@/lib/utils";

type LoadState = "loading" | "ready" | "unavailable";

function formatSize(bytes: number | null): string | null {
  if (!bytes) return null;
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(0)} MB`;
}

export function ModelSelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (model: string) => void;
  className?: string;
}) {
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
        setError(err instanceof Error ? err.message : "Could not load models");
      });
  }, []);

  // Distinct from fetchModels: resets to the loading state synchronously,
  // which only makes sense from a user-triggered refresh, not on mount.
  const refresh = React.useCallback(() => {
    setState("loading");
    setError(null);
    fetchModels();
  }, [fetchModels]);

  React.useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Once models load, default to the first one if nothing is selected yet.
  React.useEffect(() => {
    if (state === "ready" && models.length > 0 && !value) {
      onChange(models[0].name);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, models]);

  if (state === "loading") {
    return <Skeleton className={cn("h-8 w-full", className)} />;
  }

  if (state === "unavailable") {
    return (
      <div className={cn("space-y-2", className)}>
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-1.5 text-xs text-destructive">
          <AlertTriangle className="size-3.5 shrink-0" />
          <span className="min-w-0 flex-1 truncate" title={error ?? undefined}>
            Ollama is unreachable
          </span>
          <Button variant="ghost" size="icon-sm" className="size-6 shrink-0" onClick={refresh} aria-label="Retry">
            <RefreshCw className="size-3.5" />
          </Button>
        </div>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className={cn("flex items-center justify-between gap-2 rounded-md border border-dashed border-border px-2.5 py-1.5", className)}>
        <span className="text-xs text-muted-foreground">No models installed</span>
        <Button variant="ghost" size="icon-sm" className="size-6" onClick={refresh} aria-label="Refresh">
          <RefreshCw className="size-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Select value={value || undefined} onValueChange={(next) => next && onChange(next)}>
        <SelectTrigger className="flex-1">
          <SelectValue placeholder="Select a model" />
        </SelectTrigger>
        <SelectContent>
          {models.map((model) => {
            const size = formatSize(model.size_bytes);
            return (
              <SelectItem key={model.name} value={model.name}>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs">{model.name}</span>
                  {(model.parameter_size || size) && (
                    <span className="text-xs text-muted-foreground">
                      {[model.parameter_size, size].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </span>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      <Button variant="ghost" size="icon-sm" className="size-8 shrink-0" onClick={refresh} aria-label="Refresh models">
        <RefreshCw className="size-3.5" />
      </Button>
    </div>
  );
}
