/**
 * A small word-level diff (classic LCS) — enough to highlight what
 * changed between two run responses. Not a general-purpose diff
 * library: no line/character granularity, no move detection.
 *
 * Capped at `MAX_WORDS` per side — LCS is O(n*m), and a long model
 * response diffed against another long response is exactly the kind of
 * accidental-quadratic-blowup case worth guarding against explicitly.
 */

export type DiffPart = { text: string; type: "same" | "added" | "removed" };

const MAX_WORDS = 400;

function tokenize(text: string): string[] {
  // Keep whitespace as its own tokens so re-joining reproduces spacing.
  return text.match(/\s+|\S+/g) ?? [];
}

export function diffWords(a: string, b: string): { left: DiffPart[]; right: DiffPart[] } {
  const wordsA = tokenize(a).slice(0, MAX_WORDS);
  const wordsB = tokenize(b).slice(0, MAX_WORDS);

  // Standard LCS table.
  const rows = wordsA.length + 1;
  const cols = wordsB.length + 1;
  const lcs: number[][] = Array.from({ length: rows }, () => new Array<number>(cols).fill(0));
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      lcs[i][j] =
        wordsA[i - 1] === wordsB[j - 1] ? lcs[i - 1][j - 1] + 1 : Math.max(lcs[i - 1][j], lcs[i][j - 1]);
    }
  }

  const left: DiffPart[] = [];
  const right: DiffPart[] = [];
  let i = wordsA.length;
  let j = wordsB.length;
  const leftRev: DiffPart[] = [];
  const rightRev: DiffPart[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && wordsA[i - 1] === wordsB[j - 1]) {
      leftRev.push({ text: wordsA[i - 1], type: "same" });
      rightRev.push({ text: wordsB[j - 1], type: "same" });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || lcs[i][j - 1] >= lcs[i - 1][j])) {
      rightRev.push({ text: wordsB[j - 1], type: "added" });
      j--;
    } else if (i > 0) {
      leftRev.push({ text: wordsA[i - 1], type: "removed" });
      i--;
    }
  }

  left.push(...leftRev.reverse());
  right.push(...rightRev.reverse());
  return { left, right };
}
