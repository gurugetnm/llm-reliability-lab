"use client";

import * as React from "react";
import { Plus } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { parseJsonOrString, stringifyJsonValue } from "@/lib/json-field";
import { api, ApiError, type DatasetItem } from "@/lib/api";

/** Shared create/edit form for a dataset item — rendered either from a
 * trigger button (create) or from an externally-controlled `open` state
 * (edit, triggered by clicking a table row). */
export function DatasetItemDialog({
  datasetId,
  item,
  open: controlledOpen,
  onOpenChange,
  onSaved,
}: {
  datasetId: string;
  item?: DatasetItem;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onSaved: (item: DatasetItem) => void;
}) {
  const isEdit = Boolean(item);
  const [internalOpen, setInternalOpen] = React.useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  const [input, setInput] = React.useState("");
  const [expectedOutput, setExpectedOutput] = React.useState("");
  const [metadata, setMetadata] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    // Resetting the form to the target item (or blank, for "add") when the
    // dialog opens is the whole point of this effect — not a derived value
    // React could compute during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInput(item ? stringifyJsonValue(item.input) : "");
    setExpectedOutput(item ? stringifyJsonValue(item.expected_output) : "");
    setMetadata(item?.metadata ? JSON.stringify(item.metadata, null, 2) : "");
  }, [open, item]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;

    let metadataValue: Record<string, unknown> | null = null;
    if (metadata.trim()) {
      try {
        metadataValue = JSON.parse(metadata);
      } catch {
        toast.error("Metadata must be valid JSON");
        return;
      }
    }

    setSubmitting(true);
    try {
      const payload = {
        input: parseJsonOrString(input),
        expected_output: expectedOutput.trim() ? parseJsonOrString(expectedOutput) : null,
        metadata: metadataValue,
      };
      const saved = item
        ? await api.updateDatasetItem(datasetId, item.id, payload)
        : await api.createDatasetItem(datasetId, payload);
      toast.success(isEdit ? "Item updated" : "Item added");
      onSaved(saved);
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save item");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!isEdit && controlledOpen === undefined ? (
        <DialogTrigger render={<Button size="sm" />}>
          <Plus className="size-4" />
          Add Item
        </DialogTrigger>
      ) : null}
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit item" : "Add item"}</DialogTitle>
            <DialogDescription>
              Plain text or JSON — text that parses as JSON is stored as that value.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="item-input">Input</Label>
              <Textarea
                id="item-input"
                placeholder="What is TCP?"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                rows={4}
                className="font-mono text-xs"
                autoFocus
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-expected-output">Expected output (optional)</Label>
              <Textarea
                id="item-expected-output"
                placeholder="A transport protocol"
                value={expectedOutput}
                onChange={(event) => setExpectedOutput(event.target.value)}
                rows={3}
                className="font-mono text-xs"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="item-metadata">Metadata (optional JSON object)</Label>
              <Textarea
                id="item-metadata"
                placeholder={'{ "topic": "networking" }'}
                value={metadata}
                onChange={(event) => setMetadata(event.target.value)}
                rows={2}
                className="font-mono text-xs"
              />
            </div>
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
            <Button type="submit" disabled={submitting || !input.trim()}>
              {submitting ? "Saving…" : isEdit ? "Save changes" : "Add item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
