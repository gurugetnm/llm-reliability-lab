"use client";

import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { EvaluationResult } from "@/lib/api";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </h3>
      {children}
    </div>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap break-words">
      {children}
    </pre>
  );
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

/** Evaluator-specific detail views (Part 31): semantic_similarity shows
 * similarity/threshold, llm_judge shows per-criterion scores and usage,
 * contains shows matched/missing terms — everything else falls back to
 * a plain JSON dump of `details`. */
function DetailsView({ result }: { result: EvaluationResult }) {
  const d = result.details;

  if (result.evaluator.startsWith("semantic_similarity") && typeof d.similarity === "number") {
    return (
      <div className="grid grid-cols-2 gap-4">
        <Field label="Similarity">
          <p className="text-lg font-semibold tabular-nums">{d.similarity.toFixed(4)}</p>
        </Field>
        <Field label="Threshold">
          <p className="text-lg font-semibold tabular-nums">
            {typeof d.threshold === "number" ? d.threshold.toFixed(4) : "—"}
          </p>
        </Field>
        {typeof d.embedding_model === "string" ? (
          <Field label="Embedding model">
            <p className="font-mono text-xs">{d.embedding_model}</p>
          </Field>
        ) : null}
      </div>
    );
  }

  if (result.evaluator.startsWith("llm_judge") && d.criteria && typeof d.criteria === "object") {
    const criteria = d.criteria as Record<string, number>;
    const scale = typeof d.score_scale === "number" ? d.score_scale : null;
    const usage = d.usage as Record<string, number | null> | undefined;
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {Object.entries(criteria).map(([name, score]) => (
            <div key={name} className="rounded-md border border-border px-3 py-2">
              <p className="text-xs text-muted-foreground capitalize">{name}</p>
              <p className="text-sm font-semibold tabular-nums">
                {score}
                {scale ? ` / ${scale}` : ""}
              </p>
            </div>
          ))}
        </div>
        {typeof d.judge_model === "string" ? (
          <Field label="Judge model">
            <p className="font-mono text-xs">{d.judge_model}</p>
          </Field>
        ) : null}
        {usage ? (
          <Field label="Judge usage">
            <p className="text-xs text-muted-foreground">
              {usage.total_tokens ?? "?"} tokens ({usage.input_tokens ?? "?"} in /{" "}
              {usage.output_tokens ?? "?"} out)
              {typeof d.latency_ms === "number" ? ` · ${Math.round(d.latency_ms)}ms` : ""}
            </p>
          </Field>
        ) : null}
      </div>
    );
  }

  if (result.evaluator.startsWith("contains") && Array.isArray(d.matched_terms)) {
    return (
      <div className="space-y-2">
        <Field label="Matched terms">
          <div className="flex flex-wrap gap-1">
            {(d.matched_terms as string[]).map((term) => (
              <Badge key={term} variant="outline" className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                {term}
              </Badge>
            ))}
            {(d.matched_terms as string[]).length === 0 ? (
              <span className="text-xs text-muted-foreground">None</span>
            ) : null}
          </div>
        </Field>
        <Field label="Missing terms">
          <div className="flex flex-wrap gap-1">
            {((d.missing_terms as string[]) ?? []).map((term) => (
              <Badge key={term} variant="outline" className="border-destructive/30 text-destructive">
                {term}
              </Badge>
            ))}
            {((d.missing_terms as string[]) ?? []).length === 0 ? (
              <span className="text-xs text-muted-foreground">None</span>
            ) : null}
          </div>
        </Field>
      </div>
    );
  }

  return <Pre>{stringify(d)}</Pre>;
}

export function EvaluationResultDetailSheet({
  result,
  onOpenChange,
}: {
  result: EvaluationResult | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={Boolean(result)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-xl">
        {result ? (
          <>
            <SheetHeader>
              <SheetTitle>Evaluation result</SheetTitle>
              <SheetDescription>
                {result.status} · {result.evaluator}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-4 overflow-y-auto p-4 pt-0">
              <Field label="Input">
                <Pre>{stringify(result.input)}</Pre>
              </Field>
              <Field label="Expected Output">
                <Pre>{stringify(result.expected_output)}</Pre>
              </Field>
              <Field label="Actual Output">
                <Pre>{result.actual_output ?? stringify(result.actual_structured_output)}</Pre>
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Score">
                  <p className="text-lg font-semibold tabular-nums">
                    {result.score === null ? "—" : result.score.toFixed(4)}
                  </p>
                </Field>
                <Field label="Passed">
                  <p className="text-lg font-semibold">
                    {result.passed === null ? "—" : result.passed ? "Yes" : "No"}
                  </p>
                </Field>
              </div>

              {result.status === "failed" ? (
                <Field label="Error">
                  <Pre>{result.error_message ?? "No error message recorded."}</Pre>
                </Field>
              ) : (
                <>
                  {result.reason ? (
                    <Field label="Reason">
                      <p className="text-sm">{result.reason}</p>
                    </Field>
                  ) : null}
                  <Field label="Details">
                    <DetailsView result={result} />
                  </Field>
                </>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
