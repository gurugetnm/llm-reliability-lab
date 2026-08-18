import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvaluationsPage from "@/app/evaluations/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, listEvaluations: vi.fn(), getEvaluationMetrics: vi.fn() },
  };
});

const listEvaluations = vi.mocked(api.listEvaluations);
const getEvaluationMetrics = vi.mocked(api.getEvaluationMetrics);

const baseEvaluation = {
  id: "eval-1",
  run_id: "run-1",
  name: "Exact match check",
  status: "completed" as const,
  evaluator_type: "exact_match",
  evaluator_version: "v1",
  configuration: {},
  total_items: 3,
  completed_items: 3,
  successful_items: 3,
  failed_items: 0,
  cancel_requested: false,
  concurrency: 3,
  started_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
};

beforeEach(() => {
  listEvaluations.mockReset();
  getEvaluationMetrics.mockReset();
});

describe("EvaluationsPage", () => {
  it("shows a loading skeleton while evaluations are being fetched", () => {
    listEvaluations.mockReturnValue(new Promise(() => {}));
    const { container } = render(<EvaluationsPage />);
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });

  it("shows an empty state when there are no evaluations", async () => {
    listEvaluations.mockResolvedValue({ items: [], page: 1, page_size: 50, total: 0 });
    render(<EvaluationsPage />);
    expect(await screen.findByText(/no evaluation runs yet/i)).toBeInTheDocument();
  });

  it("shows an error state with retry when the request fails", async () => {
    listEvaluations.mockRejectedValue(new Error("boom"));
    render(<EvaluationsPage />);
    expect(await screen.findByText(/couldn't load evaluations/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders evaluation rows with evaluator, status, mean score, and pass rate", async () => {
    listEvaluations.mockResolvedValue({ items: [baseEvaluation], page: 1, page_size: 50, total: 1 });
    getEvaluationMetrics.mockResolvedValue({
      evaluation_run_id: "eval-1",
      total: 3,
      evaluated: 3,
      failed: 0,
      passed: 2,
      pass_rate: 0.6667,
      mean_score: 0.667,
      median_score: 1,
      min_score: 0,
      max_score: 1,
      distribution: null,
    });
    render(<EvaluationsPage />);

    expect(await screen.findByText("Exact match check")).toBeInTheDocument();
    expect(screen.getByText("exact_match:v1")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(await screen.findByText("0.67")).toBeInTheDocument();
    expect(await screen.findByText("67%")).toBeInTheDocument();
  });
});
