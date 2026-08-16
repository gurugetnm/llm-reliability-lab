"use client";

import * as React from "react";
import { Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, type Dataset, type DatasetImportRowError } from "@/lib/api";

const PLACEHOLDER: Record<"json" | "jsonl", string> = {
  json: `[
  { "input": "What is TCP?", "expected_output": "A transport protocol" },
  { "input": "What is DNS?" }
]`,
  jsonl: `{"input":"What is TCP?","expected_output":"A transport protocol"}
{"input":"What is DNS?"}`,
};

export function ImportDatasetDialog({
  datasetId,
  onImported,
}: {
  datasetId: string;
  onImported: (dataset: Dataset) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [format, setFormat] = React.useState<"json" | "jsonl">("jsonl");
  const [content, setContent] = React.useState("");
  const [errors, setErrors] = React.useState<DatasetImportRowError[]>([]);
  const [submitting, setSubmitting] = React.useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!content.trim()) return;

    setSubmitting(true);
    setErrors([]);
    try {
      const result = await api.importDatasetItems(datasetId, format, content);
      toast.success(`Imported ${result.imported_count} item(s)`);
      onImported(result.dataset);
      setOpen(false);
      setContent("");
    } catch (error) {
      if (error instanceof ApiError && Array.isArray((error.body as { errors?: unknown })?.errors)) {
        setErrors((error.body as { errors: DatasetImportRowError[] }).errors);
        toast.error("Import failed validation — see details below");
      } else {
        toast.error(error instanceof ApiError ? error.message : "Import failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setErrors([]);
      }}
    >
      <DialogTrigger render={<Button size="sm" variant="outline" />}>
        <Upload className="size-4" />
        Import
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Import items</DialogTitle>
            <DialogDescription>
              Every record is validated before anything is imported — if any record is
              invalid, nothing is added.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <Tabs value={format} onValueChange={(value) => setFormat(value as "json" | "jsonl")}>
              <TabsList>
                <TabsTrigger value="jsonl">JSONL</TabsTrigger>
                <TabsTrigger value="json">JSON array</TabsTrigger>
              </TabsList>
            </Tabs>
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={PLACEHOLDER[format]}
              rows={10}
              spellCheck={false}
              className="resize-y font-mono text-xs"
              autoFocus
            />
            {errors.length > 0 ? (
              <div className="max-h-40 overflow-y-auto rounded-md border border-destructive/30 bg-destructive/5 p-2.5 text-xs text-destructive">
                {errors.map((error, index) => (
                  <div key={index}>
                    Line {error.line}: {error.message}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !content.trim()}>
              {submitting ? "Importing…" : "Import"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
