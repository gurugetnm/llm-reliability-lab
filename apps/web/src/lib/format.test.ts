import { describe, expect, it } from "vitest";
import { formatDistanceToNow } from "@/lib/format";

describe("formatDistanceToNow", () => {
  it("formats a timestamp a few minutes in the past", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(fiveMinutesAgo)).toBe("5 minutes ago");
  });

  it("formats a timestamp a few hours in the past", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(threeHoursAgo)).toBe("3 hours ago");
  });

  it("formats a future timestamp", () => {
    const inTwoDays = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatDistanceToNow(inTwoDays)).toBe("in 2 days");
  });
});
