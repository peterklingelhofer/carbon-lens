import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CarbonIntensity, CloudRegion, RouteResponse } from "../api/types";
import { RegionComparison } from "./RegionComparison";

vi.mock("../api/client", () => ({
  api: { regions: vi.fn(), carbonIntensity: vi.fn(), route: vi.fn() },
}));

import { api } from "../api/client";

const mockRegions = vi.mocked(api.regions);
const mockIntensity = vi.mocked(api.carbonIntensity);
const mockRoute = vi.mocked(api.route);

afterEach(() => vi.clearAllMocks());

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function region(r: string): CloudRegion {
  return { provider: "aws", region: r, grid_zone: "Z", location: r, latitude: 0, longitude: 0 };
}
function intensity(v: number): CarbonIntensity {
  return {
    grid_zone: "US-MIDA-PJM",
    carbon_intensity_gco2_kwh: v,
    renewable_percentage: 30,
    timestamp: "2026-06-15T00:00:00Z",
    source: "test",
  };
}
function route(provider: string, reg: string, v: number): RouteResponse {
  return {
    recommended: {
      provider,
      region: reg,
      grid_zone: "FR",
      carbon_intensity_gco2_kwh: v,
      renewable_percentage: 70,
      score: 0,
      carbon_savings_vs_worst_pct: 0,
    },
    alternatives: [],
    request_id: "r",
    timestamp: "2026-06-15T00:00:00Z",
  };
}

describe("RegionComparison", () => {
  it("shows the carbon savings of switching to the greenest region", async () => {
    mockRegions.mockResolvedValue([region("us-east-1")]);
    mockIntensity.mockResolvedValue(intensity(400)); // current: dirty
    mockRoute.mockResolvedValue(route("scaleway", "fr-par", 100)); // greenest: clean

    renderWithClient(<RegionComparison />);

    // (400 - 100) / 400 = 75%
    expect(await screen.findByText(/~75%/)).toBeTruthy();
    // Greenest region appears (in both the stat card and the savings banner).
    expect(screen.getAllByText(/scaleway\/fr-par/).length).toBeGreaterThanOrEqual(1);
  });

  it("says you're already greenest when current is the recommendation", async () => {
    mockRegions.mockResolvedValue([region("us-east-1")]);
    mockIntensity.mockResolvedValue(intensity(100));
    mockRoute.mockResolvedValue(route("aws", "us-east-1", 100)); // same as current

    renderWithClient(<RegionComparison />);
    expect(await screen.findByText(/already on the greenest/)).toBeTruthy();
  });
});
