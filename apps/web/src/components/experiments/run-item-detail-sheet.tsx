"use client";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { RunItem } from "@/lib/api";

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

export function RunItemDetailSheet({
  item,
  onOpenChange,
}: {
  item: RunItem | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={Boolean(item)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-xl">
        {item ? (
          <>
            <SheetHeader>
              <SheetTitle>Run item</SheetTitle>
              <SheetDescription>
                {item.status} · {item.model}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-4 overflow-y-auto p-4 pt-0">
              {item.system_prompt ? (
                <Field label="System Prompt">
                  <Pre>{item.system_prompt}</Pre>
                </Field>
              ) : null}
              <Field label="User Prompt">
                <Pre>{item.user_prompt}</Pre>
              </Field>
              {item.status === "failed" ? (
                <Field label="Error">
                  <div className="space-y-1">
                    {item.error_type ? (
                      <span className="inline-block rounded bg-destructive/10 px-1.5 py-0.5 font-mono text-[11px] text-destructive">
                        {item.error_type}
                      </span>
                    ) : null}
                    <Pre>{item.error_message ?? "No error message recorded."}</Pre>
                  </div>
                </Field>
              ) : (
                <Field label="Response">
                  <Pre>
                    {item.structured_output
                      ? JSON.stringify(item.structured_output, null, 2)
                      : (item.response ?? "—")}
                  </Pre>
                </Field>
              )}

              <div className="grid grid-cols-2 gap-4">
                <Field label="Latency">
                  <p className="text-sm">
                    {item.latency_ms ? `${Math.round(item.latency_ms)}ms` : "—"}
                  </p>
                </Field>
                <Field label="Tokens">
                  <p className="text-sm">
                    {item.total_tokens
                      ? `${item.total_tokens} (${item.input_tokens ?? "?"} in / ${item.output_tokens ?? "?"} out)`
                      : "Unavailable"}
                  </p>
                </Field>
              </div>

              <Field label="Generation Parameters">
                <Pre>{JSON.stringify(item.generation_config, null, 2)}</Pre>
              </Field>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
