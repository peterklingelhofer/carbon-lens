import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import type { SitingRecommendation } from "../api/types";

vi.mock("../api/client", () => ({
  api: { siting: vi.fn() },
}));

import { api } from "../api/client";
import { SitingPicker } from "./SitingPicker";

const mockSiting = vi.mocked(api.siting);

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("SitingPicker", () => {
  it("renders the ranked regions and the annual savings", async () => {
    const rec: SitingRecommendation = {
      recommended: {
        provider: "gcp",
        region: "europe-north1",
        grid_zone: "FI",
        location: "Finland",
        typical_gco2_kwh: 70,
        basis: "history",
        annual_kg: 306,
      },
      options: [
        {
          provider: "gcp",
          region: "europe-north1",
          grid_zone: "FI",
          location: "Finland",
          typical_gco2_kwh: 70,
          basis: "history",
          annual_kg: 306,
        },
      ],
      annual_kg_saved_vs_worst: 1200,
      power_watts: 500,
      days_analyzed: 30,
    };
    mockSiting.mockResolvedValue(rec);
    renderWithClient(<SitingPicker />);

    expect((await screen.findAllByText(/europe-north1/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/1200 kg CO₂\/yr/)).toBeTruthy();
  });
});
