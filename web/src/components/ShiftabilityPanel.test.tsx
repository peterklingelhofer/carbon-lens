import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import type { ShiftabilityRanking } from "../api/types";

vi.mock("../api/client", () => ({
  api: { shiftability: vi.fn() },
}));

import { api } from "../api/client";
import { ShiftabilityPanel } from "./ShiftabilityPanel";

const mockShiftability = vi.mocked(api.shiftability);

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const ranking = (zones: ShiftabilityRanking["zones"]): ShiftabilityRanking => ({
  days_analyzed: 14,
  zones,
});

describe("ShiftabilityPanel", () => {
  it("renders the ranked zones with their savings", async () => {
    mockShiftability.mockResolvedValue(
      ranking([
        {
          grid_zone: "US-CAL-CISO",
          location: "California",
          shift_savings_pct: 62,
          cleanest_hour_utc: 13,
          dirtiest_hour_utc: 2,
          samples: 120,
        },
      ]),
    );
    renderWithClient(<ShiftabilityPanel />);

    expect(await screen.findByText("US-CAL-CISO")).toBeTruthy();
    expect(screen.getByText("62%")).toBeTruthy();
  });

  it("renders nothing when there is no data", async () => {
    mockShiftability.mockResolvedValue(ranking([]));
    const { container } = renderWithClient(<ShiftabilityPanel />);
    await waitFor(() => expect(container.querySelector("div")).toBeNull());
  });
});
