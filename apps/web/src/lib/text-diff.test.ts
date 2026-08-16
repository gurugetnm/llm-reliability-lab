import { describe, expect, it } from "vitest";
import { diffWords } from "@/lib/text-diff";

describe("diffWords", () => {
  it("marks identical text as entirely unchanged", () => {
    const { left, right } = diffWords("hello world", "hello world");
    expect(left.every((p) => p.type === "same")).toBe(true);
    expect(right.every((p) => p.type === "same")).toBe(true);
  });

  it("marks a changed word as removed on the left and added on the right", () => {
    const { left, right } = diffWords("the cat sat", "the dog sat");
    expect(left.some((p) => p.type === "removed" && p.text === "cat")).toBe(true);
    expect(right.some((p) => p.type === "added" && p.text === "dog")).toBe(true);
    expect(left.some((p) => p.type === "same" && p.text === "the")).toBe(true);
    expect(right.some((p) => p.type === "same" && p.text === "sat")).toBe(true);
  });

  it("handles one side being empty", () => {
    const { left, right } = diffWords("", "new text");
    expect(left).toEqual([]);
    expect(right.every((p) => p.type === "added" || p.type === "same")).toBe(true);
  });

  it("reassembling the parts reproduces the original text", () => {
    const a = "The quick brown fox";
    const b = "The slow brown fox jumps";
    const { left, right } = diffWords(a, b);
    expect(left.map((p) => p.text).join("")).toBe(a);
    expect(right.map((p) => p.text).join("")).toBe(b);
  });
});
