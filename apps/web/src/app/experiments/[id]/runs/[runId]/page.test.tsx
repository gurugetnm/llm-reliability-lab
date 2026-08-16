import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunDetailPage from "@/app/experiments/[id]/runs/[runId]/page";
import { api } from "@/lib/api";
import { streamRunEvents } from "@/lib/runs/events";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "exp-1", runId: "run-1" }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getExperiment: vi.fn(),
      getRun: vi.fn(),
      listRunItems: vi.fn(),
      cancelRun: vi.fn(),
    },
  };
});

vi.mock("@/lib/runs/events", () => ({
  streamRunEvents: vi.fn(),
}));

const getExperiment = vi.mocked(api.getExperiment);
const getRun = vi.mocked(api.getRun);
const listRunItems = vi.mocked(api.listRunItems);
const cancelRun = vi.mocked(api.cancelRun);
const mockStreamRunEvents = vi.mocked(streamRunEvents);

const runningRun = {
  id: "run-1",
  experiment_id: "exp-1",
  status: "running" as const,
  started_at: new Date().toISOString(),
  completed_at: null,
  total_items: 4,
  completed_items: 1,
  successful_items: 1,
  failed_items: 0,
  cancel_requested: false,
  model: "qwen2.5:0.5b",
  generation_config: { temperature: 0.7 },
  concurrency: 3,
  created_at: new Date().toISOString(),
};

beforeEach(() => {
  getExperiment.mockReset().mockResolvedValue({
    id: "exp-1",
    project_id: "p1",
    name: "Baseline",
    description: null,
    dataset: { id: "d1", name: "Set", item_count: 4 },
    system_prompt: null,
    user_prompt_template: "{{input}}",
    model: "qwen2.5:0.5b",
    generation_config: { temperature: 0.7 },
    structured_output_config: null,
    latest_run: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
  getRun.mockReset();
  listRunItems.mockReset().mockResolvedValue({ items: [], page: 1, page_size: 25, total: 0 });
  cancelRun.mockReset();
  mockStreamRunEvents.mockReset();
  mockStreamRunEvents.mockImplementation(async function* () {
    /* no events by default — individual tests provide their own */
  });
});

describe("RunDetailPage", () => {
  it("renders the run's current progress", async () => {
    getRun.mockResolvedValue(runningRun);

    render(<RunDetailPage />);

    expect(await screen.findByText("Running")).toBeInTheDocument();
    expect(screen.getByText("1 / 4 items")).toBeInTheDocument();
  });

  it("updates progress live from SSE events", async () => {
    getRun.mockResolvedValue(runningRun);
    mockStreamRunEvents.mockImplementation(async function* () {
      yield {
        type: "run_progress",
        data: {
          run_id: "run-1",
          status: "running",
          total_items: 4,
          completed_items: 3,
          successful_items: 3,
          failed_items: 0,
        },
      };
      yield {
        type: "run_completed",
        data: {
          run_id: "run-1",
          status: "completed",
          total_items: 4,
          completed_items: 4,
          successful_items: 4,
          failed_items: 0,
        },
      };
    });

    render(<RunDetailPage />);

    await waitFor(() => expect(screen.getByText("4 / 4 items")).toBeInTheDocument());
    expect(await screen.findByText("Completed")).toBeInTheDocument();
  });

  it("lets the user cancel an active run", async () => {
    getRun.mockResolvedValue(runningRun);
    cancelRun.mockResolvedValue({ ...runningRun, cancel_requested: true });
    const user = userEvent.setup();

    render(<RunDetailPage />);

    const cancelButton = await screen.findByRole("button", { name: /cancel run/i });
    await user.click(cancelButton);

    expect(cancelRun).toHaveBeenCalledWith("run-1");
  });

  it("does not show a cancel button for a completed run", async () => {
    getRun.mockResolvedValue({ ...runningRun, status: "completed" });

    render(<RunDetailPage />);

    await screen.findByText("Completed");
    expect(screen.queryByRole("button", { name: /cancel run/i })).not.toBeInTheDocument();
  });

  it("shows an empty state when the run has no items yet", async () => {
    getRun.mockResolvedValue(runningRun);

    render(<RunDetailPage />);

    expect(await screen.findByText(/no items yet/i)).toBeInTheDocument();
  });
});
