import { describe, expect, it } from "vitest";
import { validateSchemaText } from "@/components/playground/schema-editor";

describe("validateSchemaText", () => {
  it("rejects empty input", () => {
    expect(validateSchemaText("")).toMatch(/required/i);
    expect(validateSchemaText("   ")).toMatch(/required/i);
  });

  it("rejects malformed JSON", () => {
    expect(validateSchemaText("{not valid json")).toBeTruthy();
  });

  it("rejects a JSON value that isn't an object", () => {
    expect(validateSchemaText("[1, 2, 3]")).toMatch(/object/i);
    expect(validateSchemaText('"a string"')).toMatch(/object/i);
  });

  it("accepts a well-formed schema object", () => {
    const schema = JSON.stringify({
      type: "object",
      properties: { summary: { type: "string" } },
      required: ["summary"],
    });
    expect(validateSchemaText(schema)).toBeNull();
  });
});
