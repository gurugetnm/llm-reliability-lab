import type { ExecutionResult } from "@/lib/llm/types";

/**
 * Lightweight execution history, kept in localStorage only. This is
 * intentionally not persisted server-side — the permanent experiment
 * run schema is designed in Phase 3; this is just a convenience for
 * revisiting what you tried in this browser during this phase.
 */

const STORAGE_KEY = "llm-reliability-lab:playground-history";
const MAX_ENTRIES = 20;

export interface HistoryEntry {
  id: string;
  model: string;
  systemPrompt: string;
  userPrompt: string;
  responseSchemaText: string | null;
  temperature: number;
  maxTokens: number | null;
  response: string;
  structuredOutput: Record<string, unknown> | null;
  latencyMs: number;
  usage: ExecutionResult["usage"];
  createdAt: string;
}

export function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

export function saveHistoryEntry(entry: HistoryEntry): HistoryEntry[] {
  const next = [entry, ...loadHistory()].slice(0, MAX_ENTRIES);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export function clearHistory(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}
