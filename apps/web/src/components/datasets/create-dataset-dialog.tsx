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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, type Dataset, type Project } from "@/lib/api";

export function CreateDatasetDialog({
  defaultProjectId,
  onCreated,
}: {
  defaultProjectId?: string;
  onCreated?: (dataset: Dataset) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [projectId, setProjectId] = React.useState(defaultProjectId ?? "");
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    api
      .listProjects()
      .then((data) => {
        setProjects(data);
        if (!projectId && data.length > 0) setProjectId(defaultProjectId ?? data[0].id);
      })
      .catch(() => setProjects([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !projectId) return;

    setSubmitting(true);
    try {
      const dataset = await api.createDataset({
        project_id: projectId,
        name: name.trim(),
        description: description.trim() || undefined,
      });
      toast.success(`Dataset "${dataset.name}" created`);
      onCreated?.(dataset);
      setOpen(false);
      setName("");
      setDescription("");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create dataset");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>
        <Plus className="size-4" />
        Create Dataset
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create dataset</DialogTitle>
            <DialogDescription>
              A dataset holds the items an experiment will run against.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="dataset-project">Project</Label>
              {projects.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Create a project first before adding datasets.
                </p>
              ) : (
                <Select
                  value={projectId || undefined}
                  onValueChange={(value) => value && setProjectId(value)}
                >
                  <SelectTrigger id="dataset-project" className="w-full">
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map((project) => (
                      <SelectItem key={project.id} value={project.id}>
                        {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="dataset-name">Name</Label>
              <Input
                id="dataset-name"
                placeholder="e.g. Support Q&A golden set"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="dataset-description">Description (optional)</Label>
              <Textarea
                id="dataset-description"
                placeholder="What does this dataset cover?"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
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
            <Button type="submit" disabled={submitting || !name.trim() || !projectId}>
              {submitting ? "Creating…" : "Create dataset"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
