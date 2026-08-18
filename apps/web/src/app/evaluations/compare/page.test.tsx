import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CompareEvaluationsPage from "@/app/evaluations/compare/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("baseline=eval-a&candidate=eval-b"),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, listEvaluations: vi.fn(), compareEvaluations: vi.fn() },
  };
});

const listEvaluations = vi.mocked(api.listEvaluations);
const compareEvaluations = vi.mocked(api.compareEvaluations);

function makeEvaluation(id: string, name: string) {
  return {
    id,
    run_id: "run-1",
    name,
    status: "completed" as const,
    evaluator_type: "semantic_similarity",
    evaluator_version: "v1",
    configuration: {},
    total_items: 1,
    completed_items: 1,
    successful_items: 1,
    failed_items: 0,
    cancel_requested: false,
    concurrency: 3,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  };
}

function makeMetrics(mean: number, passRate: number) {
  return {
    evaluation_run_id: "x",
    total: 1,
    evaluated: 1,
    failed: 0,
    passed: 1,
    pass_rate: passRate,
    mean_score: mean,
    median_score: mean,
    min_score: mean,
    max_score: mean,
    distribution: null,
  };
}

beforeEach(() => {
  listEvaluations.mockReset();
  compareEvaluations.mockReset();
  listEvaluations.mockResolvedValue({
    items: [makeEvaluation("eval-a", "Qwen 3"), makeEvaluation("eval-b", "Llama")],
    page: 1,
    page_size: 100,
    total: 2,
  });
});

describe("CompareEvaluationsPage", () => {
  it("shows a regression-detected banner when the candidate scores lower", async () => {
    compareEvaluations.mockResolvedValue({
      baseline: makeEvaluation("eval-a", "Qwen 3"),
      candidate: makeEvaluation("eval-b", "Llama"),
      baseline_metrics: makeMetrics(0.91, 0.9),
      candidate_metrics: makeMetrics(0.84, 0.7),
      regression: {
        baseline_score: 0.91,
        candidate_score: 0.84,
        difference: -0.07,
        relative_difference: -0.077,
        threshold: 0.05,
        higher_is_better: true,
        regression_detected: true,
      },
      items: [
        {
          dataset_item_id: "di-1",
          baseline_result_id: "r-a",
          candidate_result_id: "r-b",
          baseline_score: 0.95,
          candidate_score: 0.6,
          difference: -0.35,
        },
      ],
    });

    render(<CompareEvaluationsPage />);

    expect(await screen.findByText("Regression detected")).toBeInTheDocument();
    expect(screen.getByText("Qwen 3")).toBeInTheDocument();
    expect(screen.getByText("Llama")).toBeInTheDocument();
    expect(screen.getByText("0.910")).toBeInTheDocument();
    expect(screen.getByText("0.840")).toBeInTheDocument();
  });

  it("shows a no-regression banner when the candidate improves", async () => {
    compareEvaluations.mockResolvedValue({
      baseline: makeEvaluation("eval-a", "Qwen 3"),
      candidate: makeEvaluation("eval-b", "Llama"),
      baseline_metrics: makeMetrics(0.5, 0.5),
      candidate_metrics: makeMetrics(0.9, 0.9),
      regression: {
        baseline_score: 0.5,
        candidate_score: 0.9,
        difference: 0.4,
        relative_difference: 0.8,
        threshold: 0.05,
        higher_is_better: true,
        regression_detected: false,
      },
      items: [],
    });

    render(<CompareEvaluationsPage />);

    expect(await screen.findByText("No regression detected")).toBeInTheDocument();
  });

  it("always renders the baseline/candidate pickers", async () => {
    compareEvaluations.mockResolvedValue({
      baseline: makeEvaluation("eval-a", "Qwen 3"),
      candidate: makeEvaluation("eval-b", "Llama"),
      baseline_metrics: makeMetrics(0.5, 0.5),
      candidate_metrics: makeMetrics(0.5, 0.5),
      regression: null,
      items: [],
    });
    render(<CompareEvaluationsPage />);
    expect(screen.getByText("Baseline")).toBeInTheDocument();
    expect(screen.getByText("Candidate")).toBeInTheDocument();
  });
});
