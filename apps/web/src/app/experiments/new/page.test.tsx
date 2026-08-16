import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewExperimentPage from "@/app/experiments/new/page";
import { api } from "@/lib/api";
import { llm } from "@/lib/llm/client";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, listDatasets: vi.fn(), createExperiment: vi.fn() },
  };
});

vi.mock("@/lib/llm/client", () => ({
  llm: { listModels: vi.fn() },
}));

const listDatasets = vi.mocked(api.listDatasets);
const createExperiment = vi.mocked(api.createExperiment);
const listModels = vi.mocked(llm.listModels);

beforeEach(() => {
  push.mockReset();
  listDatasets.mockReset().mockResolvedValue([
    {
      id: "d1",
      project_id: "p1",
      name: "Q&A set",
      description: null,
      version: 1,
      item_count: 10,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ]);
  listModels.mockReset().mockResolvedValue([
    {
      name: "qwen2.5:0.5b",
      provider: "ollama",
      size_bytes: null,
      modified_at: null,
      parameter_size: null,
      quantization: null,
      family: null,
      capabilities: null,
    },
  ]);
  createExperiment.mockReset();
});

describe("NewExperimentPage", () => {
  it("creates an experiment with the selected dataset, model, and prompts", async () => {
    createExperiment.mockResolvedValue({
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
    });
    const user = userEvent.setup();

    render(<NewExperimentPage />);

    await user.type(await screen.findByLabelText(/^name$/i), "Baseline");

    // Model and dataset each auto-select as the only option available
    // (mirrors ModelSelect's own convention) — proven by the submit
    // button becoming enabled without interacting with either dropdown.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /create experiment/i })).toBeEnabled(),
    );

    await user.click(screen.getByRole("button", { name: /create experiment/i }));

    await waitFor(() =>
      expect(createExperiment).toHaveBeenCalledWith(
        expect.objectContaining({
          project_id: "p1",
          dataset_id: "d1",
          name: "Baseline",
          model: "qwen2.5:0.5b",
          user_prompt_template: "{{input}}",
        }),
      ),
    );
    expect(push).toHaveBeenCalledWith("/experiments/exp-1");
  });

  it("disables submission until the required fields are filled", async () => {
    render(<NewExperimentPage />);

    expect(await screen.findByRole("button", { name: /create experiment/i })).toBeDisabled();
  });

  it("shows a warning when the selected dataset has no items", async () => {
    listDatasets.mockResolvedValue([
      {
        id: "d2",
        project_id: "p1",
        name: "Empty set",
        description: null,
        version: 1,
        item_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    render(<NewExperimentPage />);

    // Auto-selected as the only dataset available.
    expect(await screen.findByText(/has no items yet/i)).toBeInTheDocument();
  });
});
