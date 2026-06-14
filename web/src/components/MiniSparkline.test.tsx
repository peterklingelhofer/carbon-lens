import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MiniSparkline, trendLabel } from "./MiniSparkline";

describe("trendLabel", () => {
  it("labels direction with a 5% deadband", () => {
    expect(trendLabel(100, 80)).toBe("cleaner (-20%)");
    expect(trendLabel(100, 130)).toBe("dirtier (+30%)");
    expect(trendLabel(100, 102)).toBe("steady"); // within the deadband
    expect(trendLabel(0, 50)).toBe("steady"); // no baseline -> steady
  });
});

describe("MiniSparkline", () => {
  it("draws a polyline through every point and marks the chosen end", () => {
    const { container } = render(
      <MiniSparkline values={[100, 200, 50]} mark="first" ariaLabel="spark" />,
    );
    const poly = container.querySelector("polyline");
    expect(poly).not.toBeNull();
    expect(poly?.getAttribute("points")?.split(" ").length).toBe(3); // 3 points
    expect(container.querySelector("circle")).not.toBeNull(); // marker dot
    expect(container.querySelector("svg")?.getAttribute("aria-label")).toBe("spark");
  });

  it("omits the marker dot when mark is unset", () => {
    const { container } = render(<MiniSparkline values={[1, 2]} ariaLabel="x" />);
    expect(container.querySelector("circle")).toBeNull();
  });
});
