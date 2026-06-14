import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { NotFound } from "./NotFound";

describe("NotFound", () => {
  it("renders the heading and helpful destination links", () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /page not found/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /live globe/i }).getAttribute("href")).toBe("/globe");
    expect(screen.getByRole("link", { name: /methodology/i }).getAttribute("href")).toBe(
      "/methodology",
    );
    expect(screen.getByRole("link", { name: /back to home/i }).getAttribute("href")).toBe("/");
  });
});
