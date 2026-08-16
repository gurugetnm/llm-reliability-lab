import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ExperimentsPage from "@/app/experiments/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, listExperiments: vi.fn(), startRun: vi.fn() },
  };
});

const listExperiments = vi.mocked(api.listExperiments);
const startRun = vi.mocked(api.startRun);

const baseExperiment = {
  id: "exp-1",
  project_id: "p1",
  name: "Baseline",
  description: null,
  dataset: { id: "d1", name: "Q&A set", item_count: 10 },
  system_prompt: null,
  user_prompt_template: "{{input}}",
  model: "qwen2.5:0.5b",
  generation_config: { temperature: 0.7 },
  structured_output_config: null,
  latest_run: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

beforeEach(() => {
  listExperiments.mockReset();
  startRun.mockReset();
});

describe("ExperimentsPage", () => {
  it("shows a loading skeleton while experiments are being fetched", () => {
    listExperiments.mockReturnValue(new Promise(() => {}));
    const { container } = render(<ExperimentsPage />);
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });

  it("shows an empty state when there are no experiments", async () => {
    listExperiments.mockResolvedValue([]);
    render(<ExperimentsPage />);
    expect(await screen.findByText(/no experiments yet/i)).toBeInTheDocument();
  });

  it("shows an error state with retry when the request fails", async () => {
    listExperiments.mockRejectedValue(new Error("boom"));
    render(<ExperimentsPage />);
    expect(await screen.findByText(/couldn't reach the api/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders experiment rows with dataset, model, and latest run status", async () => {
    listExperiments.mockResolvedValue([
      {
        ...baseExperiment,
        latest_run: {
          id: "run-1",
          status: "completed",
          total_items: 10,
          completed_items: 10,
          successful_items: 10,
          failed_items: 0,
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        },
      },
    ]);
    render(<ExperimentsPage />);

    expect(await screen.findByText("Baseline")).toBeInTheDocument();
    expect(screen.getByText(/Q&A set/)).toBeInTheDocument();
    expect(screen.getByText("qwen2.5:0.5b")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("starts a run when the Run button is clicked", async () => {
    listExperiments.mockResolvedValue([baseExperiment]);
    startRun.mockResolvedValue({
      id: "run-2",
      experiment_id: "exp-1",
      status: "pending",
      started_at: null,
      completed_at: null,
      total_items: 10,
      completed_items: 0,
      successful_items: 0,
      failed_items: 0,
      cancel_requested: false,
      model: "qwen2.5:0.5b",
      generation_config: { temperature: 0.7 },
      concurrency: 3,
      created_at: new Date().toISOString(),
    });
    const user = userEvent.setup();
    render(<ExperimentsPage />);

    await user.click(await screen.findByRole("button", { name: /^run$/i }));

    expect(startRun).toHaveBeenCalledWith("exp-1");
  });

  it("disables the Run button when the dataset has no items", async () => {
    listExperiments.mockResolvedValue([
      { ...baseExperiment, dataset: { ...baseExperiment.dataset, item_count: 0 } },
    ]);
    render(<ExperimentsPage />);

    expect(await screen.findByRole("button", { name: /^run$/i })).toBeDisabled();
  });
});
