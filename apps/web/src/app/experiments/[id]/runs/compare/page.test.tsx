import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CompareRunsPage from "@/app/experiments/[id]/runs/compare/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("a=run-a&b=run-b"),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, getRun: vi.fn(), listRunItems: vi.fn() },
  };
});

const getRun = vi.mocked(api.getRun);
const listRunItems = vi.mocked(api.listRunItems);

function makeRun(id: string, model: string) {
  return {
    id,
    experiment_id: "exp-1",
    status: "completed" as const,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    total_items: 1,
    completed_items: 1,
    successful_items: 1,
    failed_items: 0,
    cancel_requested: false,
    model,
    generation_config: { temperature: 0.2 },
    concurrency: 3,
    created_at: new Date().toISOString(),
  };
}

function makeItem(runId: string, response: string) {
  return {
    id: `item-${runId}`,
    run_id: runId,
    dataset_item_id: "di-1",
    status: "succeeded" as const,
    model: "m",
    system_prompt: null,
    user_prompt: "Explain TCP",
    response,
    structured_output: null,
    error_type: null,
    error_message: null,
    latency_ms: 120,
    input_tokens: 5,
    output_tokens: 10,
    total_tokens: 15,
    generation_config: { temperature: 0.2 },
    created_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  };
}

beforeEach(() => {
  getRun.mockReset();
  listRunItems.mockReset();
});

describe("CompareRunsPage", () => {
  it("shows both runs' responses for the same dataset item side by side", async () => {
    getRun.mockImplementation(async (id: string) =>
      id === "run-a" ? makeRun("run-a", "qwen2.5:0.5b") : makeRun("run-b", "llama3.2:1b"),
    );
    listRunItems.mockImplementation(async (runId: string) => ({
      items: [makeItem(runId, runId === "run-a" ? "A transport protocol" : "A network protocol")],
      page: 1,
      page_size: 200,
      total: 1,
    }));

    render(<CompareRunsPage />);

    expect(await screen.findByText("qwen2.5:0.5b")).toBeInTheDocument();
    expect(screen.getByText("llama3.2:1b")).toBeInTheDocument();
    expect(screen.getByText("Explain TCP")).toBeInTheDocument();
  });
});
