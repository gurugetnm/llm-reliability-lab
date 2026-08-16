/**
 * Client-side preview of `app/experiments/prompt_template.py`'s
 * `{{variable}}` substitution — deliberately just enough to show what a
 * template will render to, not a validator. The backend is the source
 * of truth for what's actually a legal template.
 */
export function renderPromptPreview(template: string, exampleInput: string): string {
  return template.replace(/\{\{\s*input\s*\}\}/g, exampleInput);
}
