import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CarbonForecast, CarbonHistory } from "../api/types";
import { RegionForecast, RegionHistory } from "./RegionDetail";

// Mock the HTTP client so the container components resolve from fixtures, not a
// real fetch. vi.mock is hoisted, so the import below receives the mock.
vi.mock("../api/client", () => ({
  api: {
    carbonHistory: vi.fn(),
    carbonForecast: vi.fn(),
  },
}));

import { api } from "../api/client";

const mockHistory = vi.mocked(api.carbonHistory);
const mockForecast = vi.mocked(api.carbonForecast);

afterEach(() => {
  vi.clearAllMocks();
});

// Fresh QueryClient per render (retry off so error/empty states settle at once).
function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function history(points: number[]): CarbonHistory {
  return {
    grid_zone: "US-NW-BPAT",
    provider: "aws",
    region: "us-west-2",
    points: points.map((c) => ({
      timestamp: "2026-06-14T00:00:00+00:00",
      carbon_intensity_gco2_kwh: c,
      renewable_percentage: 50,
    })),
  };
}

function forecast(points: number[], method: string): CarbonForecast {
  return {
    grid_zone: "US-NW-BPAT",
    provider: "aws",
    region: "us-west-2",
    generated_at: "2026-06-14T00:00:00+00:00",
    method,
    points: points.map((c) => ({
      grid_zone: "US-NW-BPAT",
      carbon_intensity_gco2_kwh: c,
      renewable_percentage: 50,
      timestamp: "2026-06-14T00:00:00+00:00",
      source: "test",
    })),
  };
}

describe("RegionHistory", () => {
  it("renders the sparkline and reading count when history exists", async () => {
    mockHistory.mockResolvedValue(history([300, 250, 200]));
    renderWithClient(<RegionHistory provider="aws" region="us-west-2" />);

    expect(await screen.findByText(/3 readings/)).toBeTruthy();
    expect(screen.getByText("Past 7 days")).toBeTruthy();
    expect(mockHistory).toHaveBeenCalledWith("aws", "us-west-2", 168);
  });

  it("shows the accumulating note when there aren't enough points yet", async () => {
    mockHistory.mockResolvedValue(history([300]));
    renderWithClient(<RegionHistory provider="aws" region="us-west-2" />);

    expect(await screen.findByText("History is still accumulating.")).toBeTruthy();
  });
});

describe("RegionForecast", () => {
  it("renders the curve and names the forecast method", async () => {
    mockForecast.mockResolvedValue(forecast([300, 280, 250], "entsoe_day_ahead"));
    renderWithClient(<RegionForecast provider="aws" region="eu-west-3" />);

    expect(await screen.findByText(/ENTSO-E day-ahead/)).toBeTruthy();
    expect(screen.getByText("Next 24h")).toBeTruthy();
    expect(mockForecast).toHaveBeenCalledWith("aws", "eu-west-3", 24);
  });

  it("labels the heuristic method outside the EU", async () => {
    mockForecast.mockResolvedValue(forecast([300, 320], "time_of_day_model"));
    renderWithClient(<RegionForecast provider="aws" region="us-west-2" />);

    expect(await screen.findByText(/time-of-day model/)).toBeTruthy();
  });

  it("renders nothing once a too-short forecast settles", async () => {
    mockForecast.mockResolvedValue(forecast([300], "time_of_day_model"));
    renderWithClient(<RegionForecast provider="aws" region="us-west-2" />);

    await waitFor(() => expect(screen.queryByText("Loading forecast…")).toBeNull());
    expect(screen.queryByText("Next 24h")).toBeNull();
  });
});
