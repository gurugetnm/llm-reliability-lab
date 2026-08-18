/**
 * Minimal typed client for the LLM Reliability Lab API.
 *
 * Kept deliberately small for this foundation phase: a couple of REST
 * calls against `/api/v1`. As the surface grows, this should be split
 * per-resource rather than turned into a generic fetch wrapper.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    /** The full parsed error body, for endpoints that attach extra
     * fields alongside `detail` (e.g. `raw_response` on a structured
     * output validation failure). */
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  version: number;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetCreate {
  project_id: string;
  name: string;
  description?: string;
}

export interface DatasetUpdate {
  name?: string;
  description?: string;
}

export interface DatasetItem {
  id: string;
  dataset_id: string;
  input: unknown;
  expected_output: unknown;
  metadata: Record<string, unknown> | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetItemCreate {
  input: unknown;
  expected_output?: unknown;
  metadata?: Record<string, unknown> | null;
}

export interface DatasetItemUpdate {
  input?: unknown;
  expected_output?: unknown;
  metadata?: Record<string, unknown> | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface DatasetImportRowError {
  line: number;
  message: string;
}

export interface DatasetImportResponse {
  dataset: Dataset;
  imported_count: number;
}

export interface GenerationConfig {
  temperature: number;
  max_tokens?: number | null;
  top_p?: number | null;
  stop?: string[] | null;
  seed?: number | null;
}

export interface StructuredOutputConfig {
  schema: Record<string, unknown>;
}

export type ExperimentRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export interface DatasetSummary {
  id: string;
  name: string;
  item_count: number;
}

export interface RunSummary {
  id: string;
  status: ExperimentRunStatus;
  total_items: number;
  completed_items: number;
  successful_items: number;
  failed_items: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  dataset: DatasetSummary;
  system_prompt: string | null;
  user_prompt_template: string;
  model: string;
  generation_config: GenerationConfig;
  structured_output_config: StructuredOutputConfig | null;
  latest_run: RunSummary | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentCreate {
  project_id: string;
  dataset_id: string;
  name: string;
  description?: string;
  system_prompt?: string;
  user_prompt_template: string;
  model: string;
  generation_config?: GenerationConfig;
  structured_output_config?: StructuredOutputConfig | null;
}

export interface ExperimentUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
  user_prompt_template?: string;
  model?: string;
  generation_config?: GenerationConfig;
  structured_output_config?: StructuredOutputConfig | null;
}

export interface ExperimentRun {
  id: string;
  experiment_id: string;
  status: ExperimentRunStatus;
  started_at: string | null;
  completed_at: string | null;
  total_items: number;
  completed_items: number;
  successful_items: number;
  failed_items: number;
  cancel_requested: boolean;
  model: string;
  generation_config: GenerationConfig;
  concurrency: number;
  created_at: string;
}

export type RunItemStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export type RunItemErrorType =
  | "provider_error"
  | "timeout"
  | "validation_error"
  | "prompt_render_error"
  | "structured_output_error"
  | "unknown_error";

export interface RunItem {
  id: string;
  run_id: string;
  dataset_item_id: string | null;
  status: RunItemStatus;
  model: string;
  system_prompt: string | null;
  user_prompt: string;
  response: string | null;
  structured_output: Record<string, unknown> | null;
  error_type: RunItemErrorType | null;
  error_message: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  generation_config: GenerationConfig;
  created_at: string;
  completed_at: string | null;
}

// --- Evaluation engine (Phase 4) -------------------------------------------

export interface EvaluatorInfo {
  name: string;
  version: string;
  description: string;
  score_range: [number, number] | null;
  higher_is_better: boolean;
  supports_pass_fail: boolean;
  config_schema: Record<string, unknown>;
  requires_embedding_provider: boolean;
  requires_llm_provider: boolean;
}

export type EvaluationRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export type EvaluationResultStatus = "succeeded" | "failed" | "cancelled";

export interface EvaluationRunCreate {
  run_id: string;
  name: string;
  evaluator_type: string;
  configuration?: Record<string, unknown>;
  concurrency?: number;
}

export interface EvaluationRun {
  id: string;
  run_id: string;
  name: string;
  status: EvaluationRunStatus;
  evaluator_type: string;
  evaluator_version: string;
  configuration: Record<string, unknown>;
  total_items: number;
  completed_items: number;
  successful_items: number;
  failed_items: number;
  cancel_requested: boolean;
  concurrency: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvaluationResult {
  id: string;
  evaluation_run_id: string;
  run_item_id: string;
  status: EvaluationResultStatus;
  metric_name: string;
  score: number | null;
  passed: boolean | null;
  reason: string | null;
  details: Record<string, unknown>;
  evaluator: string;
  error_message: string | null;
  created_at: string;
  input: unknown;
  expected_output: unknown;
  actual_output: string | null;
  actual_structured_output: Record<string, unknown> | null;
}

export interface DistributionBucket {
  range_start: number;
  range_end: number;
  item_count: number;
}

export interface EvaluationMetrics {
  evaluation_run_id: string;
  total: number;
  evaluated: number;
  failed: number;
  passed: number | null;
  pass_rate: number | null;
  mean_score: number | null;
  median_score: number | null;
  min_score: number | null;
  max_score: number | null;
  distribution: DistributionBucket[] | null;
}

export interface Regression {
  baseline_score: number;
  candidate_score: number;
  difference: number;
  relative_difference: number | null;
  threshold: number;
  higher_is_better: boolean;
  regression_detected: boolean;
}

export interface EvaluationItemComparison {
  dataset_item_id: string | null;
  baseline_result_id: string | null;
  candidate_result_id: string | null;
  baseline_score: number | null;
  candidate_score: number | null;
  difference: number | null;
}

export interface EvaluationComparison {
  baseline: EvaluationRun;
  candidate: EvaluationRun;
  baseline_metrics: EvaluationMetrics;
  candidate_metrics: EvaluationMetrics;
  regression: Regression | null;
  items: EvaluationItemComparison[];
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Could not reach the API at ${API_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    // `detail` is usually our own AppError's message (a string), but
    // FastAPI's own request-validation errors (a malformed query param,
    // an out-of-range value the route caught before our code ever ran)
    // return `detail` as a *list* of error objects instead — coercing
    // that into an Error's `message` would silently stringify to
    // "[object Object]" rather than showing anything useful.
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(
      detail ?? `Request failed with status ${response.status}`,
      response.status,
      body,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  listProjects: () => request<Project[]>("/api/v1/projects"),
  createProject: (data: ProjectCreate) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),

  listDatasets: (projectId?: string) =>
    request<Dataset[]>(
      `/api/v1/datasets${projectId ? `?project_id=${projectId}` : ""}`,
    ),
  getDataset: (id: string) => request<Dataset>(`/api/v1/datasets/${id}`),
  createDataset: (data: DatasetCreate) =>
    request<Dataset>("/api/v1/datasets", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateDataset: (id: string, data: DatasetUpdate) =>
    request<Dataset>(`/api/v1/datasets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteDataset: (id: string) =>
    request<void>(`/api/v1/datasets/${id}`, { method: "DELETE" }),

  listDatasetItems: (datasetId: string, page = 1, pageSize = 20) =>
    request<Page<DatasetItem>>(
      `/api/v1/datasets/${datasetId}/items?page=${page}&page_size=${pageSize}`,
    ),
  createDatasetItem: (datasetId: string, data: DatasetItemCreate) =>
    request<DatasetItem>(`/api/v1/datasets/${datasetId}/items`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateDatasetItem: (datasetId: string, itemId: string, data: DatasetItemUpdate) =>
    request<DatasetItem>(`/api/v1/datasets/${datasetId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteDatasetItem: (datasetId: string, itemId: string) =>
    request<void>(`/api/v1/datasets/${datasetId}/items/${itemId}`, {
      method: "DELETE",
    }),
  importDatasetItems: (datasetId: string, format: "json" | "jsonl", content: string) =>
    request<DatasetImportResponse>(`/api/v1/datasets/${datasetId}/import`, {
      method: "POST",
      body: JSON.stringify({ format, content }),
    }),

  listExperiments: (projectId?: string) =>
    request<Experiment[]>(
      `/api/v1/experiments${projectId ? `?project_id=${projectId}` : ""}`,
    ),
  getExperiment: (id: string) => request<Experiment>(`/api/v1/experiments/${id}`),
  createExperiment: (data: ExperimentCreate) =>
    request<Experiment>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateExperiment: (id: string, data: ExperimentUpdate) =>
    request<Experiment>(`/api/v1/experiments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteExperiment: (id: string) =>
    request<void>(`/api/v1/experiments/${id}`, { method: "DELETE" }),

  startRun: (experimentId: string, concurrency?: number) =>
    request<ExperimentRun>(`/api/v1/experiments/${experimentId}/runs`, {
      method: "POST",
      body: JSON.stringify(concurrency ? { concurrency } : {}),
    }),
  listRuns: (experimentId: string, page = 1, pageSize = 20) =>
    request<Page<ExperimentRun>>(
      `/api/v1/experiments/${experimentId}/runs?page=${page}&page_size=${pageSize}`,
    ),
  getRun: (runId: string) => request<ExperimentRun>(`/api/v1/runs/${runId}`),
  listRunItems: (runId: string, page = 1, pageSize = 20) =>
    request<Page<RunItem>>(`/api/v1/runs/${runId}/items?page=${page}&page_size=${pageSize}`),
  cancelRun: (runId: string) =>
    request<ExperimentRun>(`/api/v1/runs/${runId}/cancel`, { method: "POST" }),

  listEvaluators: () => request<EvaluatorInfo[]>("/api/v1/evaluators"),
  createEvaluation: (data: EvaluationRunCreate) =>
    request<EvaluationRun>("/api/v1/evaluations", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listEvaluations: (runId?: string, page = 1, pageSize = 20) =>
    request<Page<EvaluationRun>>(
      `/api/v1/evaluations?page=${page}&page_size=${pageSize}${runId ? `&run_id=${runId}` : ""}`,
    ),
  getEvaluation: (evaluationId: string) =>
    request<EvaluationRun>(`/api/v1/evaluations/${evaluationId}`),
  listEvaluationResults: (evaluationId: string, page = 1, pageSize = 20) =>
    request<Page<EvaluationResult>>(
      `/api/v1/evaluations/${evaluationId}/results?page=${page}&page_size=${pageSize}`,
    ),
  getEvaluationMetrics: (evaluationId: string) =>
    request<EvaluationMetrics>(`/api/v1/evaluations/${evaluationId}/metrics`),
  cancelEvaluation: (evaluationId: string) =>
    request<EvaluationRun>(`/api/v1/evaluations/${evaluationId}/cancel`, { method: "POST" }),
  compareEvaluations: (baselineId: string, candidateId: string, regressionThreshold?: number) =>
    request<EvaluationComparison>(
      `/api/v1/evaluations/compare?baseline_id=${baselineId}&candidate_id=${candidateId}` +
        (regressionThreshold !== undefined ? `&regression_threshold=${regressionThreshold}` : ""),
    ),
};
