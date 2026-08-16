"use client";

import * as React from "react";
import Link from "next/link";
import { Database } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { CreateDatasetDialog } from "@/components/datasets/create-dataset-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDistanceToNow } from "@/lib/format";
import { api, ApiError, type Dataset } from "@/lib/api";

export default function DatasetsPage() {
  const [datasets, setDatasets] = React.useState<Dataset[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    api
      .listDatasets()
      .then((data) => {
        setDatasets(data);
        setError(null);
      })
      .catch((err) => {
        setDatasets([]);
        setError(err instanceof ApiError ? err.message : "Failed to load datasets");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Datasets"
        description="Manage evaluation datasets and RAG document collections."
        actions={
          <CreateDatasetDialog
            onCreated={(dataset) => setDatasets((prev) => [dataset, ...(prev ?? [])])}
          />
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t reach the API</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {datasets === null ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-36 rounded-lg" />
          <Skeleton className="h-36 rounded-lg" />
          <Skeleton className="h-36 rounded-lg" />
        </div>
      ) : datasets.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No datasets yet"
          description="Create a dataset, add items to it, and use it as the input for an experiment run."
          action={
            <CreateDatasetDialog
              onCreated={(dataset) => setDatasets((prev) => [dataset, ...(prev ?? [])])}
            />
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((dataset) => (
            <Link key={dataset.id} href={`/datasets/${dataset.id}`}>
              <Card className="h-full transition-colors hover:border-foreground/20">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2 text-sm font-medium">
                    <span className="truncate">{dataset.name}</span>
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] font-normal text-muted-foreground">
                      v{dataset.version}
                    </span>
                  </CardTitle>
                  <CardDescription className="line-clamp-2">
                    {dataset.description || "No description"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {dataset.item_count} {dataset.item_count === 1 ? "item" : "items"}
                    </span>
                    <span>Updated {formatDistanceToNow(dataset.updated_at)}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
