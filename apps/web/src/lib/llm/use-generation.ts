"use client";

import * as React from "react";

import { ApiError } from "@/lib/api";
import { llm } from "@/lib/llm/client";
import { streamGenerate } from "@/lib/llm/stream";
import type { ExecutionResult, GenerateRequest } from "@/lib/llm/types";

export type GenerationStatus = "idle" | "generating" | "done" | "error" | "cancelled";

export interface GenerationState {
  status: GenerationStatus;
  /** Accumulated text — the live streamed text while generating, or the final response once done. */
  text: string;
  structuredOutput: Record<string, unknown> | null;
  result: ExecutionResult | null;
  error: string | null;
  /** The raw model output, preserved when structured output failed validation. */
  rawResponse: string | null;
  startedAt: number | null;
}

const IDLE_STATE: GenerationState = {
  status: "idle",
  text: "",
  structuredOutput: null,
  result: null,
  error: null,
  rawResponse: null,
  startedAt: null,
};

/**
 * Drives a generation call — streaming for text mode, a single request
 * for structured mode (Ollama's `format` constraint isn't meaningfully
 * streamable chunk-by-chunk, so structured requests wait for the full,
 * validated response).
 */
export function useGeneration() {
  const [state, setState] = React.useState<GenerationState>(IDLE_STATE);
  const abortRef = React.useRef<AbortController | null>(null);

  const reset = React.useCallback(() => {
    abortRef.current?.abort();
    setState(IDLE_STATE);
  }, []);

  const generate = React.useCallback(async (request: GenerateRequest) => {
    abortRef.current?.abort();

    if (request.response_schema) {
      setState({ ...IDLE_STATE, status: "generating", startedAt: Date.now() });
      try {
        const result = await llm.generate(request);
        setState({
          status: "done",
          text: result.response,
          structuredOutput: result.structured_output,
          result,
          error: null,
          rawResponse: null,
          startedAt: null,
        });
      } catch (error) {
        const rawResponse =
          error instanceof ApiError && error.body && typeof error.body === "object"
            ? ((error.body as { raw_response?: string }).raw_response ?? null)
            : null;
        setState({
          ...IDLE_STATE,
          status: "error",
          error: error instanceof ApiError ? error.message : "Something went wrong.",
          rawResponse,
        });
      }
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setState({ ...IDLE_STATE, status: "generating", startedAt: Date.now() });

    let text = "";
    try {
      for await (const event of streamGenerate(request, controller.signal)) {
        if (event.type === "chunk") {
          text += event.delta;
          setState((prev) => ({ ...prev, status: "generating", text }));
        } else if (event.type === "done") {
          setState({
            status: "done",
            text: event.result.response || text,
            structuredOutput: null,
            result: event.result,
            error: null,
            rawResponse: null,
            startedAt: null,
          });
        } else if (event.type === "error") {
          setState({ ...IDLE_STATE, status: "error", error: event.detail, text });
        }
      }
    } finally {
      if (controller.signal.aborted) {
        setState((prev) => ({ ...prev, status: "cancelled" }));
      }
    }
  }, []);

  const cancel = React.useCallback(() => {
    abortRef.current?.abort();
  }, []);

  /** Shows a previously-saved result (e.g. from history) without re-running it. */
  const restore = React.useCallback((result: ExecutionResult) => {
    abortRef.current?.abort();
    setState({
      status: "done",
      text: result.response,
      structuredOutput: result.structured_output,
      result,
      error: null,
      rawResponse: null,
      startedAt: null,
    });
  }, []);

  return { state, generate, cancel, reset, restore };
}
