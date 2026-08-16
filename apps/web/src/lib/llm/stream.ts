import { API_URL } from "@/lib/api";
import type { ExecutionResult, GenerateRequest } from "@/lib/llm/types";

export type StreamEvent =
  | { type: "chunk"; delta: string; done: boolean }
  | { type: "done"; result: ExecutionResult }
  | { type: "error"; detail: string };

function parseSseBlock(raw: string): { event: string; data: string } | null {
  let event: string | undefined;
  let data: string | undefined;
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    else if (line.startsWith("data: ")) data = line.slice("data: ".length);
  }
  if (!event || data === undefined) return null;
  return { event, data };
}

/**
 * Streams `POST /api/v1/generate/stream` as an async generator of
 * `StreamEvent`s. Server-Sent Events over a plain `fetch` (not
 * `EventSource`) because we need to POST a body — `EventSource` only
 * supports GET.
 */
export async function* streamGenerate(
  body: GenerateRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/generate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    yield {
      type: "error",
      detail: `Could not reach the API at ${API_URL}. Is the backend running?`,
    };
    return;
  }

  if (!response.ok || !response.body) {
    const errorBody = await response.json().catch(() => null);
    yield {
      type: "error",
      detail: errorBody?.detail ?? `Request failed with status ${response.status}`,
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = parseSseBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);

        if (block?.event === "chunk") {
          const data = JSON.parse(block.data) as { delta: string; done: boolean };
          yield { type: "chunk", delta: data.delta, done: data.done };
        } else if (block?.event === "done") {
          yield { type: "done", result: JSON.parse(block.data) as ExecutionResult };
        } else if (block?.event === "error") {
          const data = JSON.parse(block.data) as { detail: string };
          yield { type: "error", detail: data.detail };
        }

        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    yield {
      type: "error",
      detail: "The connection was interrupted before the response finished.",
    };
  }
}
