"use client";

import * as React from "react";
import { Play } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ExecutionHistory } from "@/components/playground/execution-history";
import { ModelSelect } from "@/components/playground/model-select";
import { ParametersPanel } from "@/components/playground/parameters-panel";
import { PromptEditor } from "@/components/playground/prompt-editor";
import { ResponsePanel } from "@/components/playground/response-panel";
import { SchemaEditor, validateSchemaText } from "@/components/playground/schema-editor";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type HistoryEntry, clearHistory, loadHistory, saveHistoryEntry } from "@/lib/llm/history";
import type { ExecutionResult, GenerateRequest } from "@/lib/llm/types";
import { useGeneration } from "@/lib/llm/use-generation";

type OutputMode = "text" | "structured";

export default function PlaygroundPage() {
  const [model, setModel] = React.useState("");
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [userPrompt, setUserPrompt] = React.useState("");
  const [temperature, setTemperature] = React.useState(0.7);
  const [maxTokens, setMaxTokens] = React.useState<number | null>(null);
  const [mode, setMode] = React.useState<OutputMode>("text");
  const [schemaText, setSchemaText] = React.useState("");
  const [history, setHistory] = React.useState<HistoryEntry[]>([]);
  const [activeHistoryId, setActiveHistoryId] = React.useState<string | null>(null);

  const { state, generate, cancel, restore } = useGeneration();

  const runParamsRef = React.useRef<{
    model: string;
    systemPrompt: string;
    userPrompt: string;
    temperature: number;
    maxTokens: number | null;
    schemaText: string | null;
  } | null>(null);
  const lastSavedResultId = React.useRef<string | null>(null);

  React.useEffect(() => {
    // localStorage is only available client-side, so this can't be a
    // lazy useState initializer without risking a hydration mismatch —
    // it has to run after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
  }, []);

  // Persist to (local) history once a run actually completes.
  React.useEffect(() => {
    if (state.status !== "done" || !state.result || !runParamsRef.current) return;
    if (state.result.id === lastSavedResultId.current) return;
    lastSavedResultId.current = state.result.id;

    const params = runParamsRef.current;
    const entry: HistoryEntry = {
      id: state.result.id,
      model: params.model,
      systemPrompt: params.systemPrompt,
      userPrompt: params.userPrompt,
      responseSchemaText: params.schemaText,
      temperature: params.temperature,
      maxTokens: params.maxTokens,
      response: state.result.response,
      structuredOutput: state.result.structured_output,
      latencyMs: state.result.latency_ms,
      usage: state.result.usage,
      createdAt: state.result.created_at,
    };
    setHistory(saveHistoryEntry(entry));
    setActiveHistoryId(entry.id);
  }, [state.status, state.result]);

  const schemaError = mode === "structured" ? validateSchemaText(schemaText) : null;
  const canGenerate = Boolean(model) && Boolean(userPrompt.trim()) && !schemaError && state.status !== "generating";

  function handleGenerate() {
    if (!canGenerate) {
      if (!model) toast.error("Select a model first");
      else if (!userPrompt.trim()) toast.error("Enter a user prompt first");
      else if (schemaError) toast.error(schemaError);
      return;
    }

    const request: GenerateRequest = {
      model,
      messages: [
        ...(systemPrompt.trim() ? [{ role: "system" as const, content: systemPrompt }] : []),
        { role: "user" as const, content: userPrompt },
      ],
      temperature,
      max_tokens: maxTokens,
      response_schema: mode === "structured" ? JSON.parse(schemaText) : null,
    };

    runParamsRef.current = {
      model,
      systemPrompt,
      userPrompt,
      temperature,
      maxTokens,
      schemaText: mode === "structured" ? schemaText : null,
    };
    setActiveHistoryId(null);
    void generate(request);
  }

  function handleSelectHistory(entry: HistoryEntry) {
    setModel(entry.model);
    setSystemPrompt(entry.systemPrompt);
    setUserPrompt(entry.userPrompt);
    setTemperature(entry.temperature);
    setMaxTokens(entry.maxTokens);
    setMode(entry.responseSchemaText ? "structured" : "text");
    setSchemaText(entry.responseSchemaText ?? "");
    setActiveHistoryId(entry.id);

    const result: ExecutionResult = {
      id: entry.id,
      model: entry.model,
      provider: "ollama",
      response: entry.response,
      structured_output: entry.structuredOutput,
      finish_reason: null,
      latency_ms: entry.latencyMs,
      usage: entry.usage,
      parameters: {
        temperature: entry.temperature,
        max_tokens: entry.maxTokens,
        top_p: null,
        stop: null,
        seed: null,
      },
      created_at: entry.createdAt,
    };
    restore(result);
  }

  function handleClearHistory() {
    clearHistory();
    setHistory([]);
    setActiveHistoryId(null);
  }

  return (
    <>
      <PageHeader
        title="Playground"
        description="Run a prompt against a local model and inspect the raw result."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <div className="space-y-4 rounded-lg border border-border p-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Model</label>
            <ModelSelect value={model} onChange={setModel} />
          </div>

          <PromptEditor
            id="system-prompt"
            label="System Prompt"
            value={systemPrompt}
            onChange={setSystemPrompt}
            placeholder="Optional — instructions the model should follow throughout"
            rows={3}
            onSubmitShortcut={handleGenerate}
          />

          <PromptEditor
            id="user-prompt"
            label="User Prompt"
            value={userPrompt}
            onChange={setUserPrompt}
            placeholder="What do you want the model to do?"
            rows={8}
            onSubmitShortcut={handleGenerate}
          />

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Output</label>
            <Tabs value={mode} onValueChange={(value) => setMode(value as OutputMode)}>
              <TabsList className="w-full">
                <TabsTrigger value="text" className="flex-1">
                  Text
                </TabsTrigger>
                <TabsTrigger value="structured" className="flex-1">
                  Structured JSON
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {mode === "structured" ? (
            <SchemaEditor value={schemaText} onChange={setSchemaText} />
          ) : null}

          <ParametersPanel
            temperature={temperature}
            onTemperatureChange={setTemperature}
            maxTokens={maxTokens}
            onMaxTokensChange={setMaxTokens}
          />

          <Button className="w-full" onClick={handleGenerate} disabled={!canGenerate}>
            <Play className="size-3.5" />
            {state.status === "generating" ? "Generating…" : "Generate"}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            <kbd className="rounded border border-border px-1 py-0.5 font-mono text-[10px]">
              ⌘/Ctrl + Enter
            </kbd>{" "}
            to generate
          </p>
        </div>

        <div className="min-h-[420px] rounded-lg border border-border">
          <ResponsePanel state={state} onCancel={cancel} />
        </div>
      </div>

      {history.length > 0 ? (
        <div className="mt-4">
          <ExecutionHistory
            entries={history}
            activeId={activeHistoryId}
            onSelect={handleSelectHistory}
            onClear={handleClearHistory}
          />
        </div>
      ) : null}
    </>
  );
}
