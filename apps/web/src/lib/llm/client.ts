import { request } from "@/lib/api";
import type {
  ExecutionResult,
  GenerateRequest,
  ModelSummary,
  ModelsHealth,
} from "@/lib/llm/types";

export const llm = {
  listModels: () => request<ModelSummary[]>("/api/v1/models"),
  modelsHealth: () => request<ModelsHealth>("/api/v1/models/health"),
  generate: (body: GenerateRequest) =>
    request<ExecutionResult>("/api/v1/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
