import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { llm } from "@/lib/llm/client";
import { streamGenerate } from "@/lib/llm/stream";
import type { ExecutionResult, GenerateRequest } from "@/lib/llm/types";
import { useGeneration } from "@/lib/llm/use-generation";

vi.mock("@/lib/llm/client", () => ({
  llm: { generate: vi.fn(), listModels: vi.fn(), modelsHealth: vi.fn() },
}));
vi.mock("@/lib/llm/stream", () => ({
  streamGenerate: vi.fn(),
}));

const mockGenerate = vi.mocked(llm.generate);
const mockStreamGenerate = vi.mocked(streamGenerate);

const TEXT_REQUEST: GenerateRequest = {
  model: "llama3.1",
  messages: [{ role: "user", content: "hi" }],
  temperature: 0.7,
};

function makeResult(overrides: Partial<ExecutionResult> = {}): ExecutionResult {
  return {
    id: "exec-1",
    model: "llama3.1",
    provider: "ollama",
    response: "Hello!",
    structured_output: null,
    finish_reason: "stop",
    latency_ms: 120,
    usage: { prompt_tokens: 5, completion_tokens: 2, total_tokens: 7 },
    parameters: { temperature: 0.7, max_tokens: null, top_p: null, stop: null, seed: null },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  mockGenerate.mockReset();
  mockStreamGenerate.mockReset();
});

describe("useGeneration — streaming (text mode)", () => {
  it("accumulates chunks and lands in the done state", async () => {
    mockStreamGenerate.mockImplementation(async function* () {
      yield { type: "chunk", delta: "Hel", done: false } as const;
      yield { type: "chunk", delta: "lo", done: false } as const;
      yield { type: "done", result: makeResult({ response: "Hello" }) } as const;
    });

    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.generate(TEXT_REQUEST);
    });

    expect(result.current.state.status).toBe("done");
    expect(result.current.state.text).toBe("Hello");
    expect(result.current.state.result?.usage.total_tokens).toBe(7);
  });

  it("surfaces a stream error event without crashing", async () => {
    mockStreamGenerate.mockImplementation(async function* () {
      yield { type: "error", detail: "Model 'llama3.1' was not found" } as const;
    });

    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.generate(TEXT_REQUEST);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.error).toMatch(/was not found/);
  });

  it("marks the run cancelled and keeps partial text when stopped mid-stream", async () => {
    mockStreamGenerate.mockImplementation(async function* (_req, signal) {
      yield { type: "chunk", delta: "Hel", done: false } as const;
      await new Promise((resolve) => setTimeout(resolve, 200));
      if (signal?.aborted) return;
      yield { type: "chunk", delta: "lo", done: false } as const;
    });

    const { result } = renderHook(() => useGeneration());

    let runPromise!: Promise<void>;
    act(() => {
      runPromise = result.current.generate(TEXT_REQUEST);
    });

    await waitFor(() => expect(result.current.state.text).toBe("Hel"));
    act(() => result.current.cancel());
    await act(async () => {
      await runPromise;
    });

    expect(result.current.state.status).toBe("cancelled");
    expect(result.current.state.text).toBe("Hel");
  });
});

describe("useGeneration — structured mode", () => {
  const STRUCTURED_REQUEST: GenerateRequest = {
    ...TEXT_REQUEST,
    response_schema: { type: "object" },
  };

  it("does not stream — calls the non-streaming endpoint and stores structured_output", async () => {
    mockGenerate.mockResolvedValue(
      makeResult({ response: "", structured_output: { summary: "ok" } }),
    );

    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.generate(STRUCTURED_REQUEST);
    });

    expect(mockStreamGenerate).not.toHaveBeenCalled();
    expect(result.current.state.status).toBe("done");
    expect(result.current.state.structuredOutput).toEqual({ summary: "ok" });
  });

  it("preserves the raw response on a structured validation failure", async () => {
    mockGenerate.mockRejectedValue(
      new ApiError("Output did not match the provided schema", 422, {
        detail: "Output did not match the provided schema",
        raw_response: "not json",
      }),
    );

    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.generate(STRUCTURED_REQUEST);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.rawResponse).toBe("not json");
  });
});

describe("useGeneration — restore", () => {
  it("shows a saved result without calling the API", () => {
    const { result } = renderHook(() => useGeneration());
    const saved = makeResult({ id: "from-history" });

    act(() => result.current.restore(saved));

    expect(result.current.state.status).toBe("done");
    expect(result.current.state.result?.id).toBe("from-history");
    expect(mockGenerate).not.toHaveBeenCalled();
    expect(mockStreamGenerate).not.toHaveBeenCalled();
  });
});
