"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

/**
 * Per-evaluator configuration fields (Part 29). Hand-tailored per
 * evaluator type rather than generated generically from `config_schema`
 * — the schema is still what the backend validates against (and what
 * `GET /api/v1/evaluators` exposes for anyone building their own
 * client), but a handful of purpose-built fields per evaluator reads far
 * better than a generic JSON-Schema form for a form this small.
 */
export function EvaluatorConfigFields({
  evaluatorType,
  config,
  onChange,
}: {
  evaluatorType: string;
  config: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  function set(key: string, value: unknown) {
    onChange({ ...config, [key]: value });
  }

  switch (evaluatorType) {
    case "exact_match":
      return (
        <div className="space-y-3">
          <ToggleRow
            id="case-sensitive"
            label="Case sensitive"
            description="Compare the response and expected output with case significant."
            checked={Boolean(config.case_sensitive)}
            onCheckedChange={(v) => set("case_sensitive", v)}
          />
          <ToggleRow
            id="ignore-whitespace"
            label="Ignore whitespace"
            description="Trim and normalize line endings before comparing."
            checked={config.ignore_whitespace !== false}
            onCheckedChange={(v) => set("ignore_whitespace", v)}
          />
        </div>
      );

    case "contains":
      return (
        <div className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="required-terms">Required terms (one per line)</Label>
            <Textarea
              id="required-terms"
              rows={4}
              placeholder={"three-way handshake\nSYN\nACK"}
              value={(asStringArray(config.required_terms) ?? []).join("\n")}
              onChange={(e) =>
                set(
                  "required_terms",
                  e.target.value.split("\n").map((t) => t.trim()).filter(Boolean),
                )
              }
            />
          </div>
          <ThresholdSlider
            value={asNumber(config.threshold, 1.0)}
            onChange={(v) => set("threshold", v)}
            label="Pass threshold (fraction of terms matched)"
          />
        </div>
      );

    case "semantic_similarity":
      return (
        <div className="space-y-3">
          <ThresholdSlider
            value={asNumber(config.threshold, 0.8)}
            onChange={(v) => set("threshold", v)}
            label="Similarity threshold"
          />
          <p className="text-xs text-muted-foreground">
            Uses the server&apos;s configured local embedding model (no API key required).
          </p>
        </div>
      );

    case "llm_judge":
      return (
        <div className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="judge-model">Judge model</Label>
            <Input
              id="judge-model"
              placeholder="e.g. qwen3 — kept separate from the candidate model"
              value={asString(config.judge_model)}
              onChange={(e) => set("judge_model", e.target.value)}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="score-scale">Score scale</Label>
              <Input
                id="score-scale"
                type="number"
                min={2}
                max={10}
                value={asNumber(config.score_scale, 5)}
                onChange={(e) => set("score_scale", Number(e.target.value))}
              />
            </div>
            <ThresholdSlider
              value={asNumber(config.threshold, 0.7)}
              onChange={(v) => set("threshold", v)}
              label="Pass threshold"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="criteria">Criteria (one per line)</Label>
            <Textarea
              id="criteria"
              rows={3}
              placeholder={"accuracy\nrelevance\ncompleteness"}
              value={(asStringArray(config.criteria) ?? ["accuracy", "relevance", "completeness"]).join(
                "\n",
              )}
              onChange={(e) =>
                set(
                  "criteria",
                  e.target.value.split("\n").map((t) => t.trim()).filter(Boolean),
                )
              }
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="judge-system-prompt">Judge system prompt (optional)</Label>
            <Textarea
              id="judge-system-prompt"
              rows={3}
              placeholder="Overrides the default judge instructions"
              value={asString(config.judge_system_prompt)}
              onChange={(e) => set("judge_system_prompt", e.target.value || undefined)}
            />
          </div>
        </div>
      );

    default:
      return null;
  }
}

function ToggleRow({
  id,
  label,
  description,
  checked,
  onCheckedChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
      <div>
        <Label htmlFor={id}>{label}</Label>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

function ThresholdSlider({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <span className="text-xs tabular-nums text-muted-foreground">{value.toFixed(2)}</span>
      </div>
      <Slider
        min={0}
        max={1}
        step={0.01}
        value={[value]}
        onValueChange={(next) => onChange(Array.isArray(next) ? next[0] : next)}
        className="py-1.5"
      />
    </div>
  );
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" ? value : fallback;
}

function asStringArray(value: unknown): string[] | null {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : null;
}
