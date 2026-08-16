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
    throw new ApiError(
      body?.detail ?? `Request failed with status ${response.status}`,
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
};
