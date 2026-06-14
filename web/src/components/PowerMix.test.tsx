import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fuelMeta, PowerMix } from "./PowerMix";

describe("fuelMeta", () => {
  it("maps known fuels and falls back to grey for unknown ones", () => {
    expect(fuelMeta("wind").label).toBe("Wind");
    expect(fuelMeta("mystery")).toEqual({ label: "mystery", color: "#64748b" });
  });
});

describe("PowerMix", () => {
  it("renders nothing when there is no positive generation", () => {
    const { container } = render(<PowerMix breakdown={{}} />);
    expect(container.firstChild).toBeNull();
    const { container: c2 } = render(<PowerMix breakdown={{ wind: 0, coal: -5 }} />);
    expect(c2.firstChild).toBeNull();
  });

  it("shows fuels as percentage shares, dropping zero/negative", () => {
    render(<PowerMix breakdown={{ wind: 750, coal: 250, battery: -10 }} />);
    expect(screen.getByText("Generation mix")).toBeTruthy();
    expect(screen.getByText("Wind 75%")).toBeTruthy();
    expect(screen.getByText("Coal 25%")).toBeTruthy();
    expect(screen.queryByText(/Battery/)).toBeNull(); // negative -> dropped
  });

  it("limits the legend to the top 5 fuels by output", () => {
    render(<PowerMix breakdown={{ a: 50, b: 20, c: 15, d: 8, e: 5, f: 2 }} />);
    expect(screen.getByText("a 50%")).toBeTruthy();
    expect(screen.getByText("e 5%")).toBeTruthy();
    expect(screen.queryByText("f 2%")).toBeNull(); // 6th drops out of the legend
  });
});
