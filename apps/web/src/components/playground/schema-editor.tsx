"use client";

import * as React from "react";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const PLACEHOLDER = `{
  "type": "object",
  "properties": {
    "summary": { "type": "string" },
    "sentiment": { "type": "string" }
  },
  "required": ["summary", "sentiment"]
}`;

/** Returns null if `text` is valid JSON, otherwise a short error message. */
export function validateSchemaText(text: string): string | null {
  if (!text.trim()) return "A JSON Schema is required in structured mode";
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return "Schema must be a JSON object";
    }
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : "Invalid JSON";
  }
}

export function SchemaEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const error = value.trim() ? validateSchemaText(value) : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor="response-schema">Response JSON Schema</Label>
        {error ? <span className="text-xs text-destructive">{error}</span> : null}
      </div>
      <Textarea
        id="response-schema"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={PLACEHOLDER}
        rows={8}
        spellCheck={false}
        className={cn(
          "resize-y font-mono text-xs",
          error && "border-destructive/50 focus-visible:ring-destructive/30",
        )}
      />
    </div>
  );
}
