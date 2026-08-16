"use client";

import * as React from "react";
import { Check, Copy, Loader2, Square, TerminalSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import type { GenerationState } from "@/lib/llm/use-generation";

function useElapsed(startedAt: number | null, active: boolean): number {
  const [elapsed, setElapsed] = React.useState(0);

  React.useEffect(() => {
    if (!active || startedAt === null) {
      return;
    }
    // The first tick lags by up to 100ms (imperceptible) rather than
    // setting state synchronously here, which would fight the timer
    // that's about to take over anyway.
    const id = setInterval(() => setElapsed(Date.now() - startedAt), 100);
    return () => clearInterval(id);
  }, [active, startedAt]);

  return elapsed;
}

export function ResponsePanel({
  state,
  onCancel,
}: {
  state: GenerationState;
  onCancel: () => void;
}) {
  const [copied, setCopied] = React.useState(false);
  const elapsed = useElapsed(state.startedAt, state.status === "generating");

  const displayText = state.structuredOutput
    ? JSON.stringify(state.structuredOutput, null, 2)
    : state.text;

  async function handleCopy() {
    if (!displayText) return;
    await navigator.clipboard.writeText(displayText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (state.status === "idle") {
    return (
      <EmptyState
        icon={TerminalSquare}
        title="Nothing generated yet"
        description="Configure a model and prompt, then Generate to see the response here."
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {state.status === "generating" && (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              <span className="tabular-nums">Generating… {(elapsed / 1000).toFixed(1)}s</span>
            </>
          )}
          {state.status === "done" && state.result && (
            <span className="tabular-nums">
              Done in {(state.result.latency_ms / 1000).toFixed(1)}s
            </span>
          )}
          {state.status === "cancelled" && <span>Stopped</span>}
          {state.status === "error" && <span className="text-destructive">Generation failed</span>}
        </div>
        <div className="flex items-center gap-1">
          {state.status === "generating" ? (
            <Button variant="outline" size="sm" onClick={onCancel}>
              <Square className="size-3" />
              Stop
            </Button>
          ) : null}
          {displayText ? (
            <Button
              variant="ghost"
              size="icon-sm"
              className="size-7"
              onClick={handleCopy}
              aria-label="Copy response"
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {state.status === "error" ? (
          <div className="space-y-3">
            <p className="text-sm text-destructive">{state.error}</p>
            {state.rawResponse ? (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                  Raw model output (didn&apos;t match the schema)
                </p>
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
                  {state.rawResponse}
                </pre>
              </div>
            ) : null}
          </div>
        ) : displayText ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed">
            {displayText}
            {state.status === "generating" ? (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-middle" />
            ) : null}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground">Waiting for the first token…</p>
        )}
        {state.status === "cancelled" ? (
          <p className="mt-3 text-xs text-muted-foreground">Generation stopped before it finished.</p>
        ) : null}
      </div>

      {state.status === "done" && state.result ? (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-border px-4 py-2.5">
          <Badge variant="secondary" className="font-mono text-[11px] font-normal">
            {state.result.model}
          </Badge>
          <Badge variant="secondary" className="text-[11px] font-normal">
            {state.result.latency_ms.toFixed(0)}ms
          </Badge>
          {state.result.usage.total_tokens != null ? (
            <Badge variant="secondary" className="text-[11px] font-normal">
              {state.result.usage.prompt_tokens ?? "?"} in / {state.result.usage.completion_tokens ?? "?"} out
            </Badge>
          ) : (
            <Badge variant="secondary" className="text-[11px] font-normal text-muted-foreground">
              token usage unavailable
            </Badge>
          )}
          {state.result.finish_reason ? (
            <Badge variant="secondary" className="text-[11px] font-normal">
              {state.result.finish_reason}
            </Badge>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
