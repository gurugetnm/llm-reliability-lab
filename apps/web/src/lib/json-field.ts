/**
 * Dataset item fields (`input`, `expected_output`, `metadata`) are JSON
 * values, but most items are just plain strings ("What is TCP?") — forcing
 * users to type `"What is TCP?"` with quotes for every item would be
 * needlessly hostile. So: if the text parses as JSON, use the parsed
 * value (an object, array, number, ...); otherwise treat it as a plain
 * string. This is the same convenience real tools (e.g. `jq -R`) offer.
 */
export function parseJsonOrString(text: string): unknown {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return text;
  }
}

/** Renders a JSON value back to editable text — strings unwrap to their
 * raw form (no surrounding quotes), everything else pretty-prints. */
export function stringifyJsonValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}
