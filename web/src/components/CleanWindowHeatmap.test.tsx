import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CarbonForecast, CloudRegion } from "../api/types";
import { CleanWindowHeatmap } from "./CleanWindowHeatmap";

vi.mock("../api/client", () => ({
  api: {
    carbonForecast: vi.fn(),
    regions: vi.fn(),
  },
}));

import { api } from "../api/client";

const mockForecast = vi.mocked(api.carbonForecast);
const mockRegions = vi.mocked(api.regions);

afterEach(() => vi.clearAllMocks());

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function forecast(hours: number): CarbonForecast {
  const start = new Date("2026-06-15T00:00:00Z").getTime();
  return {
    grid_zone: "US-MIDA-PJM",
    provider: "aws",
    region: "us-east-1",
    generated_at: "2026-06-15T00:00:00Z",
    method: "time_of_day_model",
    clean_surplus_hours: [],
    points: Array.from({ length: hours }, (_, i) => ({
      grid_zone: "US-MIDA-PJM",
      carbon_intensity_gco2_kwh: 100 + (i % 24) * 5,
      renewable_percentage: 50,
      timestamp: new Date(start + i * 3600_000).toISOString(),
      source: "test",
    })),
  };
}

function region(r: string): CloudRegion {
  return { provider: "aws", region: r, grid_zone: "Z", location: r, latitude: 0, longitude: 0 };
}

describe("CleanWindowHeatmap", () => {
  it("renders a heatmap grid and the projection caption from the forecast", async () => {
    mockForecast.mockResolvedValue(forecast(48)); // ~2 local days of hourly cells
    mockRegions.mockResolvedValue([region("us-east-1"), region("us-west-2")]);

    renderWithClient(<CleanWindowHeatmap />);

    expect(await screen.findByText(/Projection from/)).toBeTruthy();
    // Each populated hour renders a coloured cell with a gCO2 tooltip.
    expect(screen.getAllByTitle(/gCO₂\/kWh/).length).toBeGreaterThanOrEqual(24);
    expect(mockForecast).toHaveBeenCalledWith("aws", "us-east-1", 168);
    // Provider switcher + region selector are present.
    expect(screen.getByRole("button", { name: "gcp" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Region" })).toBeTruthy();
  });

  it("shows an empty-state message when the forecast is unavailable", async () => {
    mockForecast.mockResolvedValue(forecast(1)); // < 2 points -> nothing to plot
    mockRegions.mockResolvedValue([region("us-east-1")]);

    renderWithClient(<CleanWindowHeatmap />);
    expect(await screen.findByText(/No forecast available/)).toBeTruthy();
  });
});
