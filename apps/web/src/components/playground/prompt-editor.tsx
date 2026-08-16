"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { estimateTokens } from "@/lib/llm/token-estimate";

export function PromptEditor({
  id,
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  onSubmitShortcut,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  /** Called on Cmd/Ctrl+Enter, so users don't have to reach for the button. */
  onSubmitShortcut?: () => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor={id}>{label}</Label>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {value ? <span>~{estimateTokens(value)} tokens</span> : null}
          {value ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="size-5"
              onClick={() => onChange("")}
              aria-label={`Clear ${label.toLowerCase()}`}
            >
              <X className="size-3" />
            </Button>
          ) : null}
        </div>
      </div>
      <Textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            onSubmitShortcut?.();
          }
        }}
        placeholder={placeholder}
        rows={rows}
        className="resize-y font-mono text-sm"
        spellCheck={false}
      />
    </div>
  );
}
