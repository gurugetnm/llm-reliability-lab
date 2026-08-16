"use client";

import { History, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { formatDistanceToNow } from "@/lib/format";
import type { HistoryEntry } from "@/lib/llm/history";
import { cn } from "@/lib/utils";

export function ExecutionHistory({
  entries,
  activeId,
  onSelect,
  onClear,
}: {
  entries: HistoryEntry[];
  activeId: string | null;
  onSelect: (entry: HistoryEntry) => void;
  onClear: () => void;
}) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <History className="size-3.5" />
          History (this browser)
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          className="size-6"
          onClick={onClear}
          aria-label="Clear history"
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
      <ScrollArea className="w-full whitespace-nowrap">
        <div className="flex gap-2 p-2.5">
          {entries.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => onSelect(entry)}
              className={cn(
                "flex w-56 shrink-0 flex-col gap-1 rounded-md border px-3 py-2 text-left transition-colors",
                entry.id === activeId
                  ? "border-primary/40 bg-accent"
                  : "border-border hover:bg-accent/60",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[11px] text-muted-foreground">
                  {entry.model}
                </span>
                <span className="shrink-0 text-[11px] text-muted-foreground">
                  {(entry.latencyMs / 1000).toFixed(1)}s
                </span>
              </div>
              <p className="line-clamp-2 text-xs">{entry.userPrompt || "(empty prompt)"}</p>
              <span className="text-[11px] text-muted-foreground">
                {formatDistanceToNow(entry.createdAt)}
              </span>
            </button>
          ))}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
    </div>
  );
}
