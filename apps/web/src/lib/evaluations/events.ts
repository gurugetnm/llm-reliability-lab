import { API_URL } from "@/lib/api";

export interface EvaluationProgressSnapshot {
  evaluation_run_id: string;
  status: string;
  total_items: number;
  completed_items: number;
  successful_items: number;
  failed_items: number;
}

export type EvaluationEvent =
  | {
      type: "evaluation_started" | "evaluation_progress" | "evaluation_completed" | "evaluation_cancelled";
      data: EvaluationProgressSnapshot;
    }
  | { type: "evaluation_item_completed" | "evaluation_item_failed"; data: Record<string, unknown> };

const TERMINAL_EVENTS = new Set(["evaluation_completed", "evaluation_cancelled"]);

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

/** Streams `GET /api/v1/evaluations/{id}/events` as an async generator of
 * typed events — the same fetch-based SSE reader `lib/runs/events.ts`
 * uses for run progress, applied to evaluation progress. */
export async function* streamEvaluationEvents(
  evaluationId: string,
  signal?: AbortSignal,
): AsyncGenerator<EvaluationEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/evaluations/${evaluationId}/events`, { signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    return;
  }
  if (!response.ok || !response.body) return;

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
        if (block) {
          yield { type: block.event, data: JSON.parse(block.data) } as EvaluationEvent;
          if (TERMINAL_EVENTS.has(block.event)) return;
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
  }
}
