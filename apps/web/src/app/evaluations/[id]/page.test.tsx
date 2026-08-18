import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvaluationDetailPage from "@/app/evaluations/[id]/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "eval-1" }),
}));

vi.mock("@/lib/evaluations/events", () => ({
  streamEvaluationEvents: async function* () {
    // no live events in this test — the evaluation is already terminal
  },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getEvaluation: vi.fn(),
      getEvaluationMetrics: vi.fn(),
      listEvaluationResults: vi.fn(),
      cancelEvaluation: vi.fn(),
    },
  };
});

const getEvaluation = vi.mocked(api.getEvaluation);
const getEvaluationMetrics = vi.mocked(api.getEvaluationMetrics);
const listEvaluationResults = vi.mocked(api.listEvaluationResults);

const baseEvaluation = {
  id: "eval-1",
  run_id: "run-1",
  name: "Exact match check",
  status: "completed" as const,
  evaluator_type: "exact_match",
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

const baseResult = {
  id: "result-1",
  evaluation_run_id: "eval-1",
  run_item_id: "item-1",
  status: "succeeded" as const,
  metric_name: "exact_match",
  score: 1.0,
  passed: true,
  reason: "Exact match.",
  details: { expected: "paris", actual: "paris" },
  evaluator: "exact_match:v1",
  error_message: null,
  created_at: new Date().toISOString(),
  input: "What is the capital of France?",
  expected_output: "Paris",
  actual_output: "Paris",
  actual_structured_output: null,
};

beforeEach(() => {
  getEvaluation.mockReset();
  getEvaluationMetrics.mockReset();
  listEvaluationResults.mockReset();
});

describe("EvaluationDetailPage", () => {
  it("shows a loading skeleton before the evaluation loads", () => {
    getEvaluation.mockReturnValue(new Promise(() => {}));
    listEvaluationResults.mockReturnValue(new Promise(() => {}));
    getEvaluationMetrics.mockReturnValue(new Promise(() => {}));
    const { container } = render(<EvaluationDetailPage />);
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });

  it("renders status, progress, metrics, and results", async () => {
    getEvaluation.mockResolvedValue(baseEvaluation);
    listEvaluationResults.mockResolvedValue({
      items: [baseResult],
      page: 1,
      page_size: 25,
      total: 1,
    });
    getEvaluationMetrics.mockResolvedValue({
      evaluation_run_id: "eval-1",
      total: 1,
      evaluated: 1,
      failed: 0,
      passed: 1,
      pass_rate: 1.0,
      mean_score: 1.0,
      median_score: 1.0,
      min_score: 1.0,
      max_score: 1.0,
      distribution: null,
    });

    render(<EvaluationDetailPage />);

    expect(await screen.findByText("Exact match check")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("1 / 1 evaluated")).toBeInTheDocument();
    expect(await screen.findByText("100%")).toBeInTheDocument(); // pass rate tile
    expect(screen.getByText(/What is the capital of France/)).toBeInTheDocument();
  });

  it("opens the result detail sheet when a row is clicked", async () => {
    getEvaluation.mockResolvedValue(baseEvaluation);
    listEvaluationResults.mockResolvedValue({
      items: [baseResult],
      page: 1,
      page_size: 25,
      total: 1,
    });
    getEvaluationMetrics.mockResolvedValue({
      evaluation_run_id: "eval-1",
      total: 1,
      evaluated: 1,
      failed: 0,
      passed: 1,
      pass_rate: 1.0,
      mean_score: 1.0,
      median_score: 1.0,
      min_score: 1.0,
      max_score: 1.0,
      distribution: null,
    });
    const user = userEvent.setup();

    render(<EvaluationDetailPage />);

    const row = await screen.findByText(/What is the capital of France/);
    await user.click(row);

    expect(await screen.findByText("Evaluation result")).toBeInTheDocument();
    expect(screen.getByText("Reason")).toBeInTheDocument();
  });

  it("shows an empty state when there are no results yet", async () => {
    getEvaluation.mockResolvedValue({ ...baseEvaluation, status: "running", total_items: 0, completed_items: 0 });
    listEvaluationResults.mockResolvedValue({ items: [], page: 1, page_size: 25, total: 0 });
    getEvaluationMetrics.mockResolvedValue({
      evaluation_run_id: "eval-1",
      total: 0,
      evaluated: 0,
      failed: 0,
      passed: null,
      pass_rate: null,
      mean_score: null,
      median_score: null,
      min_score: null,
      max_score: null,
      distribution: null,
    });

    render(<EvaluationDetailPage />);

    expect(await screen.findByText(/no results yet/i)).toBeInTheDocument();
  });
});
