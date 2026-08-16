"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ModelSelect } from "@/components/playground/model-select";
import { ParametersPanel } from "@/components/playground/parameters-panel";
import { PromptEditor } from "@/components/playground/prompt-editor";
import { SchemaEditor, validateSchemaText } from "@/components/playground/schema-editor";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { renderPromptPreview } from "@/lib/prompt-preview";
import { api, ApiError, type Dataset } from "@/lib/api";

export default function NewExperimentPage() {
  const router = useRouter();
  const [datasets, setDatasets] = React.useState<Dataset[] | null>(null);
  const [datasetId, setDatasetId] = React.useState("");
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [model, setModel] = React.useState("");
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [userPromptTemplate, setUserPromptTemplate] = React.useState("{{input}}");
  const [temperature, setTemperature] = React.useState(0.7);
  const [maxTokens, setMaxTokens] = React.useState<number | null>(null);
  const [structuredEnabled, setStructuredEnabled] = React.useState(false);
  const [schemaText, setSchemaText] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    api
      .listDatasets()
      .then(setDatasets)
      .catch(() => setDatasets([]));
  }, []);

  // Mirrors ModelSelect's own convention: default to the only option
  // rather than making the user pick from a list of one.
  React.useEffect(() => {
    if (datasets && datasets.length > 0 && !datasetId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDatasetId(datasets[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasets]);

  const selectedDataset = datasets?.find((d) => d.id === datasetId) ?? null;
  const schemaError = structuredEnabled ? validateSchemaText(schemaText) : null;
  const canSubmit =
    Boolean(datasetId) &&
    Boolean(name.trim()) &&
    Boolean(model) &&
    Boolean(userPromptTemplate.trim()) &&
    !schemaError;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || !selectedDataset) return;

    setSubmitting(true);
    try {
      const experiment = await api.createExperiment({
        project_id: selectedDataset.project_id,
        dataset_id: datasetId,
        name: name.trim(),
        description: description.trim() || undefined,
        system_prompt: systemPrompt.trim() || undefined,
        user_prompt_template: userPromptTemplate,
        model,
        generation_config: { temperature, max_tokens: maxTokens },
        structured_output_config: structuredEnabled ? { schema: JSON.parse(schemaText) } : null,
      });
      toast.success(`Experiment "${experiment.name}" created`);
      router.push(`/experiments/${experiment.id}`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create experiment");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Create Experiment"
        description="Define a reproducible model + prompt configuration to run against a dataset."
      />

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-[minmax(320px,1fr)_1fr]">
        <Card>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="experiment-dataset">Dataset</Label>
              {datasets === null ? (
                <p className="text-xs text-muted-foreground">Loading datasets…</p>
              ) : datasets.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No datasets yet — create one first on the Datasets page.
                </p>
              ) : (
                <Select value={datasetId || undefined} onValueChange={(v) => v && setDatasetId(v)}>
                  <SelectTrigger id="experiment-dataset" className="w-full">
                    <SelectValue placeholder="Select a dataset" />
                  </SelectTrigger>
                  <SelectContent>
                    {datasets.map((dataset) => (
                      <SelectItem key={dataset.id} value={dataset.id}>
                        {dataset.name} ({dataset.item_count} items)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedDataset && selectedDataset.item_count === 0 ? (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  This dataset has no items yet — add items before running this experiment.
                </p>
              ) : null}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="experiment-name">Name</Label>
              <Input
                id="experiment-name"
                placeholder="e.g. Baseline — temperature 0.2"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="experiment-description">Description (optional)</Label>
              <Textarea
                id="experiment-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={2}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>Model</Label>
              <ModelSelect value={model} onChange={setModel} />
            </div>

            <ParametersPanel
              temperature={temperature}
              onTemperatureChange={setTemperature}
              maxTokens={maxTokens}
              onMaxTokensChange={setMaxTokens}
            />

            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <div>
                <Label htmlFor="structured-toggle">Structured output</Label>
                <p className="text-xs text-muted-foreground">
                  Constrain and validate the response against a JSON Schema.
                </p>
              </div>
              <Switch
                id="structured-toggle"
                checked={structuredEnabled}
                onCheckedChange={setStructuredEnabled}
              />
            </div>
            {structuredEnabled ? (
              <SchemaEditor value={schemaText} onChange={setSchemaText} />
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-4">
              <PromptEditor
                id="experiment-system-prompt"
                label="System Prompt"
                value={systemPrompt}
                onChange={setSystemPrompt}
                placeholder="Optional — instructions the model should follow throughout"
                rows={3}
              />
              <div className="space-y-1.5">
                <PromptEditor
                  id="experiment-user-prompt-template"
                  label="User Prompt Template"
                  value={userPromptTemplate}
                  onChange={setUserPromptTemplate}
                  placeholder={"Explain the following concept simply:\n\n{{input}}"}
                  rows={6}
                />
                <p className="text-xs text-muted-foreground">
                  Use <code className="font-mono">{"{{input}}"}</code> to insert each dataset
                  item&apos;s input.
                </p>
              </div>

              {userPromptTemplate.trim() ? (
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Preview</Label>
                  <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
                    {renderPromptPreview(userPromptTemplate, "Explain TCP handshake")}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Button type="submit" className="w-full" disabled={!canSubmit || submitting}>
            {submitting ? "Creating…" : "Create Experiment"}
          </Button>
        </div>
      </form>
    </>
  );
}
