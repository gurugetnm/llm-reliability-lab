/**
 * A rough client-side heuristic (~4 characters per token for English
 * text) — not an actual tokenizer, since that's model-specific and we
 * don't have the model's real tokenizer available in the browser.
 * Always labeled as an estimate wherever it's shown.
 */
export function estimateTokens(text: string): number {
  if (!text.trim()) return 0;
  return Math.max(1, Math.round(text.length / 4));
}
