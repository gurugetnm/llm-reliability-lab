import { describe, expect, it } from "vitest";
import { parseJsonOrString, stringifyJsonValue } from "@/lib/json-field";

describe("parseJsonOrString", () => {
  it("parses valid JSON into its value", () => {
    expect(parseJsonOrString('{"a": 1}')).toEqual({ a: 1 });
    expect(parseJsonOrString("42")).toBe(42);
    expect(parseJsonOrString("true")).toBe(true);
  });

  it("falls back to the raw string when it isn't valid JSON", () => {
    expect(parseJsonOrString("What is TCP?")).toBe("What is TCP?");
  });

  it("returns null for empty input", () => {
    expect(parseJsonOrString("")).toBeNull();
    expect(parseJsonOrString("   ")).toBeNull();
  });
});

describe("stringifyJsonValue", () => {
  it("returns strings unwrapped, without quotes", () => {
    expect(stringifyJsonValue("What is TCP?")).toBe("What is TCP?");
  });

  it("pretty-prints non-string values", () => {
    expect(stringifyJsonValue({ a: 1 })).toBe('{\n  "a": 1\n}');
  });

  it("returns an empty string for null/undefined", () => {
    expect(stringifyJsonValue(null)).toBe("");
    expect(stringifyJsonValue(undefined)).toBe("");
  });
});
