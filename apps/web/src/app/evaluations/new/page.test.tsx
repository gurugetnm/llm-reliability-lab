import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewEvaluationPage from "@/app/evaluations/new/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("runId=run-1"),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, listEvaluators: vi.fn(), getRun: vi.fn(), createEvaluation: vi.fn() },
  };
});

const listEvaluators = vi.mocked(api.listEvaluators);
const getRun = vi.mocked(api.getRun);
const createEvaluation = vi.mocked(api.createEvaluation);

const evaluators = [
  {
    name: "exact_match",
    version: "v1",
    description: "Scores 1.0 on an exact match.",
    score_range: [0, 1] as [number, number],
    higher_is_better: true,
    supports_pass_fail: true,
    config_schema: {},
    requires_embedding_provider: false,
    requires_llm_provider: false,
  },
  {
    name: "llm_judge",
    version: "v1",
    description: "Uses an LLM to grade the answer.",
    score_range: [0, 1] as [number, number],
    higher_is_better: true,
    supports_pass_fail: true,
    config_schema: {},
    requires_embedding_provider: false,
    requires_llm_provider: true,
  },
];

const run = {
  id: "run-1",
  experiment_id: "exp-1",
  status: "completed" as const,
  started_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  total_items: 3,
  completed_items: 3,
  successful_items: 3,
  failed_items: 0,
  cancel_requested: false,
  model: "qwen2.5:0.5b",
  generation_config: { temperature: 0.2 },
  concurrency: 3,
  created_at: new Date().toISOString(),
};

beforeEach(() => {
  listEvaluators.mockReset();
  getRun.mockReset();
  createEvaluation.mockReset();
  listEvaluators.mockResolvedValue(evaluators);
  getRun.mockResolvedValue(run);
});

describe("NewEvaluationPage", () => {
  it("prefills the run from ?runId= and defaults to the first evaluator", async () => {
    render(<NewEvaluationPage />);

    expect(await screen.findByText("qwen2.5:0.5b")).toBeInTheDocument();
    expect(await screen.findByLabelText(/name/i)).toHaveValue("exact match evaluation");
  });

  it("disables submission for llm_judge until a judge model is entered", async () => {
    const user = userEvent.setup();
    render(<NewEvaluationPage />);

    await screen.findByText("qwen2.5:0.5b");
    await user.click(screen.getByLabelText(/evaluator type/i));
    await user.click(await screen.findByText("llm judge"));

    expect(screen.getByRole("button", { name: /start evaluation/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/judge model/i), "qwen3");
    expect(screen.getByRole("button", { name: /start evaluation/i })).toBeEnabled();
  });

  it("submits the evaluation and includes the configuration", async () => {
    createEvaluation.mockResolvedValue({
      id: "eval-1",
      run_id: "run-1",
      name: "exact match evaluation",
      status: "pending",
      evaluator_type: "exact_match",
      evaluator_version: "v1",
      configuration: {},
      total_items: 0,
      completed_items: 0,
      successful_items: 0,
      failed_items: 0,
      cancel_requested: false,
      concurrency: 3,
      started_at: null,
      completed_at: null,
      created_at: new Date().toISOString(),
    });
    const user = userEvent.setup();
    render(<NewEvaluationPage />);

    await screen.findByText("qwen2.5:0.5b");
    await user.click(screen.getByRole("button", { name: /start evaluation/i }));

    expect(createEvaluation).toHaveBeenCalledWith(
      expect.objectContaining({ run_id: "run-1", evaluator_type: "exact_match" }),
    );
  });
});
