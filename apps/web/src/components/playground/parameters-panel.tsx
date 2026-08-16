"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

export function ParametersPanel({
  temperature,
  onTemperatureChange,
  maxTokens,
  onMaxTokensChange,
}: {
  temperature: number;
  onTemperatureChange: (value: number) => void;
  maxTokens: number | null;
  onMaxTokensChange: (value: number | null) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="temperature">Temperature</Label>
          <span className="text-xs tabular-nums text-muted-foreground">
            {temperature.toFixed(1)}
          </span>
        </div>
        <Slider
          id="temperature"
          min={0}
          max={2}
          step={0.1}
          value={[temperature]}
          onValueChange={(next) => {
            const value = Array.isArray(next) ? next[0] : next;
            onTemperatureChange(value);
          }}
          className="py-1.5"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="max-tokens">Max tokens</Label>
        <Input
          id="max-tokens"
          type="number"
          min={1}
          max={32_768}
          placeholder="Model default"
          value={maxTokens ?? ""}
          onChange={(event) => {
            const raw = event.target.value;
            onMaxTokensChange(raw === "" ? null : Number(raw));
          }}
        />
      </div>
    </div>
  );
}
