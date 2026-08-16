"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { Database, Pencil, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { DatasetItemDialog } from "@/components/datasets/dataset-item-dialog";
import { ImportDatasetDialog } from "@/components/datasets/import-dataset-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "@/lib/format";
import { stringifyJsonValue } from "@/lib/json-field";
import { api, ApiError, type Dataset, type DatasetItem } from "@/lib/api";

const PAGE_SIZE = 20;

function truncate(text: string, max = 80): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();

  const [dataset, setDataset] = React.useState<Dataset | null>(null);
  const [items, setItems] = React.useState<DatasetItem[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [error, setError] = React.useState<string | null>(null);
  const [editingItem, setEditingItem] = React.useState<DatasetItem | null>(null);

  const load = React.useCallback(() => {
    setError(null);
    Promise.all([api.getDataset(id), api.listDatasetItems(id, page, PAGE_SIZE)])
      .then(([datasetResult, itemsResult]) => {
        setDataset(datasetResult);
        setItems(itemsResult.items);
        setTotal(itemsResult.total);
      })
      .catch((err) => {
        setItems([]);
        setError(err instanceof ApiError ? err.message : "Failed to load dataset");
      });
  }, [id, page]);

  React.useEffect(() => {
    // `load` sets state from an async .then, not synchronously here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function handleDelete(item: DatasetItem) {
    if (!window.confirm("Delete this item? This can't be undone.")) return;
    try {
      await api.deleteDatasetItem(id, item.id);
      toast.success("Item deleted");
      load();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to delete item");
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (error && !dataset) {
    return (
      <>
        <PageHeader title="Dataset" />
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t load this dataset</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </>
    );
  }

  if (!dataset) {
    return (
      <>
        <PageHeader title="Loading…" />
        <Skeleton className="mb-4 h-16 rounded-lg" />
        <Skeleton className="h-96 rounded-lg" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={dataset.name}
        description={dataset.description || "No description"}
        actions={
          <div className="flex items-center gap-2">
            <ImportDatasetDialog datasetId={dataset.id} onImported={() => load()} />
            <DatasetItemDialog datasetId={dataset.id} onSaved={() => load()} />
          </div>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>Version {dataset.version}</span>
        <span>
          {total} {total === 1 ? "item" : "items"}
        </span>
        <span>Created {formatDistanceToNow(dataset.created_at)}</span>
        <span>Updated {formatDistanceToNow(dataset.updated_at)}</span>
      </div>

      {items === null ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Database}
          title="This dataset contains no items"
          description="Add items one at a time or import a JSON/JSONL file."
          action={
            <div className="flex items-center justify-center gap-2">
              <DatasetItemDialog datasetId={dataset.id} onSaved={() => load()} />
              <ImportDatasetDialog datasetId={dataset.id} onImported={() => load()} />
            </div>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="w-12 px-3 py-2 text-left font-medium">#</th>
                  <th className="px-3 py-2 text-left font-medium">Input</th>
                  <th className="px-3 py-2 text-left font-medium">Expected output</th>
                  <th className="w-24 px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2 align-top text-muted-foreground">
                      {item.position}
                    </td>
                    <td className="max-w-xs px-3 py-2 align-top font-mono text-xs">
                      {truncate(stringifyJsonValue(item.input) || "—")}
                    </td>
                    <td className="max-w-xs px-3 py-2 align-top font-mono text-xs text-muted-foreground">
                      {truncate(stringifyJsonValue(item.expected_output) || "—")}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Edit item"
                          onClick={() => setEditingItem(item)}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Delete item"
                          onClick={() => handleDelete(item)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-muted-foreground">
              <span>
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {editingItem ? (
        <DatasetItemDialog
          datasetId={dataset.id}
          item={editingItem}
          open={Boolean(editingItem)}
          onOpenChange={(open) => !open && setEditingItem(null)}
          onSaved={() => {
            setEditingItem(null);
            load();
          }}
        />
      ) : null}
    </>
  );
}
