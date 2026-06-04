import { describe, expect, it } from "vitest";
import { niceKm, timeAgo } from "./format";

describe("timeAgo", () => {
  const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

  it("reports sub-minute as 'just now'", () => {
    expect(timeAgo(ago(10_000))).toBe("just now");
  });

  it("reports minutes", () => {
    expect(timeAgo(ago(5 * 60_000))).toBe("5 min ago");
  });

  it("reports hours with pluralization", () => {
    expect(timeAgo(ago(60 * 60_000))).toBe("1 hr ago");
    expect(timeAgo(ago(3 * 60 * 60_000))).toBe("3 hrs ago");
  });

  it("never goes negative for a future timestamp", () => {
    expect(timeAgo(new Date(Date.now() + 60_000).toISOString())).toBe("just now");
  });
});

describe("niceKm", () => {
  it("rounds to 1/2/5 × 10ⁿ", () => {
    expect(niceKm(1)).toBe(1);
    expect(niceKm(1.4)).toBe(1);
    expect(niceKm(3)).toBe(2);
    expect(niceKm(4)).toBe(5);
    expect(niceKm(9)).toBe(10);
    expect(niceKm(1001)).toBe(1000);
    expect(niceKm(700)).toBe(500);
  });

  it("handles non-positive input", () => {
    expect(niceKm(0)).toBe(0);
    expect(niceKm(-5)).toBe(0);
  });
});
