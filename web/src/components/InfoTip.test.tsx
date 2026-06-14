import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InfoTip } from "./InfoTip";

describe("InfoTip", () => {
  it("exposes an accessible trigger and keeps the tip hidden until opened", () => {
    render(<InfoTip label="carbon intensity" text="grams of CO2 per kWh" />);
    expect(screen.getByRole("button", { name: "What is carbon intensity?" })).toBeTruthy();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("toggles the tooltip on click", () => {
    render(<InfoTip label="x" text="the definition" />);
    const btn = screen.getByRole("button", { name: "What is x?" });
    fireEvent.click(btn);
    expect(screen.getByRole("tooltip").textContent).toContain("the definition");
    fireEvent.click(btn);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("opens on hover and closes on leave", () => {
    render(<InfoTip label="x" text="hover def" />);
    const btn = screen.getByRole("button", { name: "What is x?" });
    fireEvent.mouseEnter(btn);
    expect(screen.getByRole("tooltip").textContent).toContain("hover def");
    fireEvent.mouseLeave(btn);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
