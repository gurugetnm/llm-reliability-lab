/** Mirrors apps/api/app/schemas/{model,generation}.py — kept in sync by hand. */

export interface ModelSummary {
  name: string;
  provider: string;
  size_bytes: number | null;
  modified_at: string | null;
  parameter_size: string | null;
  quantization: string | null;
  family: string | null;
  capabilities: string[] | null;
}

export interface ModelsHealth {
  available: boolean;
  provider: string;
  model_count: number | null;
  latency_ms: number | null;
  error: string | null;
}

export type MessageRole = "system" | "user" | "assistant";

export interface GenerateMessage {
  role: MessageRole;
  content: string;
}

export interface GenerateRequest {
  model: string;
  messages: GenerateMessage[];
  temperature: number;
  max_tokens?: number | null;
  top_p?: number | null;
  seed?: number | null;
  response_schema?: Record<string, unknown> | null;
}

export interface TokenUsage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface GenerationParameters {
  temperature: number;
  max_tokens: number | null;
  top_p: number | null;
  stop: string[] | null;
  seed: number | null;
}

export interface ExecutionResult {
  id: string;
  model: string;
  provider: string;
  response: string;
  structured_output: Record<string, unknown> | null;
  finish_reason: string | null;
  latency_ms: number;
  usage: TokenUsage;
  parameters: GenerationParameters;
  created_at: string;
}
