"use client";

import * as React from "react";
import { FolderKanban } from "lucide-react";
import { formatDistanceToNow } from "@/lib/format";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, ApiError, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = React.useState<Project[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    api
      .listProjects()
      .then((data) => {
        setProjects(data);
        setError(null);
      })
      .catch((err) => {
        setProjects([]);
        setError(err instanceof ApiError ? err.message : "Failed to load projects");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Projects"
        description="Group experiments, datasets, and evaluations by project."
        actions={
          <CreateProjectDialog
            onCreated={(project) => setProjects((prev) => [project, ...(prev ?? [])])}
          />
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>Couldn&apos;t reach the API</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {projects === null ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-32 rounded-lg" />
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Create your first project to start organizing experiments, datasets, and evaluations."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardHeader>
                <CardTitle className="text-sm font-medium">{project.name}</CardTitle>
                <CardDescription>
                  {project.description || "No description"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Created {formatDistanceToNow(project.created_at)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
