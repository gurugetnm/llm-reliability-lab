import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlaygroundPage from "@/app/playground/page";
import { llm } from "@/lib/llm/client";
import { streamGenerate } from "@/lib/llm/stream";

vi.mock("@/lib/llm/client", () => ({
  llm: { listModels: vi.fn(), generate: vi.fn(), modelsHealth: vi.fn() },
}));
vi.mock("@/lib/llm/stream", () => ({
  streamGenerate: vi.fn(),
}));

const mockListModels = vi.mocked(llm.listModels);
const mockStreamGenerate = vi.mocked(streamGenerate);

beforeEach(() => {
  mockListModels.mockReset();
  mockStreamGenerate.mockReset();
  window.localStorage.clear();
});

describe("PlaygroundPage", () => {
  it("disables Generate until a model and a user prompt are present", async () => {
    mockListModels.mockResolvedValue([
      { name: "llama3.1", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
    ]);
    const user = userEvent.setup();
    render(<PlaygroundPage />);

    const generateButton = screen.getByRole("button", { name: /generate/i });
    expect(generateButton).toBeDisabled();

    await user.type(screen.getByLabelText("User Prompt"), "Say hi");

    await waitFor(() => expect(generateButton).not.toBeDisabled());
  });

  it("switches to structured mode and shows the schema editor", async () => {
    mockListModels.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<PlaygroundPage />);

    expect(screen.queryByLabelText("Response JSON Schema")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Structured JSON" }));

    expect(screen.getByLabelText("Response JSON Schema")).toBeInTheDocument();
  });

  it("keeps Generate disabled in structured mode until the schema is valid JSON", async () => {
    mockListModels.mockResolvedValue([
      { name: "llama3.1", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
    ]);
    const user = userEvent.setup();
    render(<PlaygroundPage />);

    await user.type(screen.getByLabelText("User Prompt"), "Summarize this");
    await user.click(screen.getByRole("tab", { name: "Structured JSON" }));

    const generateButton = screen.getByRole("button", { name: /generate/i });
    await waitFor(() => expect(generateButton).toBeDisabled());

    await user.type(screen.getByLabelText("Response JSON Schema"), "{{not valid json");
    expect(generateButton).toBeDisabled();
  });

  it("streams a response and renders it progressively", async () => {
    mockListModels.mockResolvedValue([
      { name: "llama3.1", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
    ]);
    mockStreamGenerate.mockImplementation(async function* () {
      yield { type: "chunk", delta: "Hi ", done: false } as const;
      yield { type: "chunk", delta: "there!", done: false } as const;
      yield {
        type: "done",
        result: {
          id: "exec-1",
          model: "llama3.1",
          provider: "ollama",
          response: "Hi there!",
          structured_output: null,
          finish_reason: "stop",
          latency_ms: 84,
          usage: { prompt_tokens: 4, completion_tokens: 3, total_tokens: 7 },
          parameters: { temperature: 0.7, max_tokens: null, top_p: null, stop: null, seed: null },
          created_at: new Date().toISOString(),
        },
      } as const;
    });

    const user = userEvent.setup();
    render(<PlaygroundPage />);

    await user.type(screen.getByLabelText("User Prompt"), "Say hi");
    await waitFor(() => expect(screen.getByRole("button", { name: /generate/i })).not.toBeDisabled());
    await user.click(screen.getByRole("button", { name: /generate/i }));

    expect(await screen.findByText("Hi there!")).toBeInTheDocument();
    expect(mockStreamGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        model: "llama3.1",
        messages: [{ role: "user", content: "Say hi" }],
      }),
      expect.anything(),
    );
  });
});
