import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BestTime, CarbonForecast, CarbonHistory, WeatherConditions } from "../api/types";
import {
  RegionBestTime,
  RegionForecast,
  RegionHistory,
  RegionSignal,
  RegionWeather,
} from "./RegionDetail";

// Mock the HTTP client so the container components resolve from fixtures, not a
// real fetch. vi.mock is hoisted, so the import below receives the mock.
vi.mock("../api/client", () => ({
  api: {
    carbonHistory: vi.fn(),
    carbonForecast: vi.fn(),
    regionWeather: vi.fn(),
    bestTime: vi.fn(),
  },
}));

// The region components read precomputed snapshot/CDN data (no API call); mock them.
vi.mock("../api/snapshot", () => ({
  useSignal: vi.fn(),
  useForecastSnapshot: vi.fn(),
  useBestTimeSnapshot: vi.fn(),
  useRegionHistoryArchive: vi.fn(),
  useWeatherSnapshot: vi.fn(),
}));

import { api } from "../api/client";
import {
  useBestTimeSnapshot,
  useForecastSnapshot,
  useRegionHistoryArchive,
  useSignal,
  useWeatherSnapshot,
} from "../api/snapshot";

const mockUseSignal = vi.mocked(useSignal);
const mockUseForecastSnapshot = vi.mocked(useForecastSnapshot);
const mockUseBestTimeSnapshot = vi.mocked(useBestTimeSnapshot);
const mockUseRegionHistoryArchive = vi.mocked(useRegionHistoryArchive);
const mockUseWeatherSnapshot = vi.mocked(useWeatherSnapshot);
const mockHistory = vi.mocked(api.carbonHistory);
const mockForecast = vi.mocked(api.carbonForecast);
const mockWeather = vi.mocked(api.regionWeather);
const mockBestTime = vi.mocked(api.bestTime);

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

function forecast(points: number[], method: string, surplusHours: number[] = []): CarbonForecast {
  return {
    grid_zone: "US-NW-BPAT",
    provider: "aws",
    region: "us-west-2",
    generated_at: "2026-06-14T00:00:00+00:00",
    method,
    clean_surplus_hours: surplusHours,
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

  it("renders from the CDN history archive without calling the API", () => {
    mockUseRegionHistoryArchive.mockReturnValue([
      { t: "2026-06-14T00:00:00+00:00", c: 300, r: 40 },
      { t: "2026-06-14T01:00:00+00:00", c: 250, r: 45 },
      { t: "2026-06-14T02:00:00+00:00", c: 200, r: 50 },
    ]);
    renderWithClient(<RegionHistory provider="gcp" region="europe-north1" />);

    expect(screen.getByText(/3 readings/)).toBeTruthy();
    expect(mockHistory).not.toHaveBeenCalled(); // served from the CDN archive
  });
});

function weather(wind: number, solar: number): WeatherConditions {
  return {
    grid_zone: "US-NW-BPAT",
    provider: "aws",
    region: "us-west-2",
    wind_speed_kmh: wind,
    solar_irradiance_w_m2: solar,
    observed_at: "2026-06-14T00:00:00+00:00",
    source: "open_meteo",
  };
}

describe("RegionWeather", () => {
  it("renders wind and solar with the driver read", async () => {
    mockWeather.mockResolvedValue(weather(24, 480));
    renderWithClient(<RegionWeather provider="aws" region="us-west-2" />);

    expect(await screen.findByText("Weather now")).toBeTruthy();
    expect(screen.getByText(/24/)).toBeTruthy();
    expect(screen.getByText(/480/)).toBeTruthy();
    expect(mockWeather).toHaveBeenCalledWith("aws", "us-west-2");
  });

  it("renders nothing when the weather fetch fails", async () => {
    mockWeather.mockRejectedValue(new Error("503"));
    const { container } = renderWithClient(<RegionWeather provider="aws" region="us-west-2" />);

    await waitFor(() => expect(container.querySelector("div")).toBeNull());
  });

  it("renders from the precomputed snapshot weather without calling the API", () => {
    mockUseWeatherSnapshot.mockReturnValue({
      wind_speed_kmh: 30,
      solar_irradiance_w_m2: 520,
      source: "open_meteo",
    });
    renderWithClient(<RegionWeather provider="gcp" region="europe-north1" />);

    expect(screen.getByText("Weather now")).toBeTruthy();
    expect(screen.getByText(/30/)).toBeTruthy();
    expect(mockWeather).not.toHaveBeenCalled(); // served from the snapshot
  });
});

function bestTime(hour: number | null, savings: number | null): BestTime {
  return {
    provider: "aws",
    region: "us-west-2",
    grid_zone: "US-NW-BPAT",
    basis: hour == null ? "insufficient" : "history",
    days_analyzed: 14,
    cleanest_hour_utc: hour,
    dirtiest_hour_utc: hour == null ? null : 18,
    shift_savings_pct: savings,
    annual_kg_saved: null,
    suggested_cron: hour == null ? null : `0 ${hour} * * *`,
    ranked_hours: hour == null ? [] : [{ hour_utc: hour, mean_gco2_kwh: 40, samples: 12 }],
  };
}

describe("RegionBestTime", () => {
  it("shows the greenest hour and a cron line", async () => {
    mockBestTime.mockResolvedValue(bestTime(3, 91));
    renderWithClient(<RegionBestTime provider="aws" region="us-west-2" />);

    expect(await screen.findByText("03:00 UTC", { exact: false })).toBeTruthy();
    expect(screen.getByText("0 3 * * *")).toBeTruthy();
    expect(screen.getByText(/91% cleaner/)).toBeTruthy();
  });

  it("renders nothing when there's no usable signal", async () => {
    mockBestTime.mockResolvedValue(bestTime(null, null));
    const { container } = renderWithClient(<RegionBestTime provider="aws" region="us-west-2" />);
    await waitFor(() => expect(container.querySelector("div")).toBeNull());
  });

  it("renders from the precomputed snapshot best-time without calling the API", () => {
    mockUseBestTimeSnapshot.mockReturnValue(bestTime(7, 64));
    renderWithClient(<RegionBestTime provider="gcp" region="europe-north1" />);

    expect(screen.getByText("07:00 UTC", { exact: false })).toBeTruthy();
    expect(screen.getByText("0 7 * * *")).toBeTruthy();
    expect(mockBestTime).not.toHaveBeenCalled(); // served from the snapshot
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

  it("flags the soonest upcoming clean-surplus window", async () => {
    mockForecast.mockResolvedValue(forecast([300, 280, 40, 35], "entsoe_day_ahead", [2, 3]));
    renderWithClient(<RegionForecast provider="aws" region="us-west-2" />);

    expect(await screen.findByText(/Clean-surplus window in ~2h/)).toBeTruthy();
  });

  it("renders nothing once a too-short forecast settles", async () => {
    mockForecast.mockResolvedValue(forecast([300], "time_of_day_model"));
    renderWithClient(<RegionForecast provider="aws" region="us-west-2" />);

    await waitFor(() => expect(screen.queryByText("Loading forecast…")).toBeNull());
    expect(screen.queryByText("Next 24h")).toBeNull();
  });

  it("renders from the precomputed snapshot curve without calling the API", () => {
    mockUseForecastSnapshot.mockReturnValue({
      grid_zone: "FI",
      provider: "gcp",
      region: "europe-north1",
      method: "entsoe_day_ahead",
      generated_at: "2026-06-14T00:00:00+00:00",
      clean_surplus_hours: [2, 3],
      points: [
        { t: "2026-06-14T00:00:00+00:00", c: 300 },
        { t: "2026-06-14T01:00:00+00:00", c: 120 },
        { t: "2026-06-14T02:00:00+00:00", c: 40 },
      ],
    });
    renderWithClient(<RegionForecast provider="gcp" region="europe-north1" />);

    expect(screen.getByText(/ENTSO-E day-ahead/)).toBeTruthy();
    expect(screen.getByText(/Clean-surplus window in ~2h/)).toBeTruthy();
    expect(mockForecast).not.toHaveBeenCalled(); // served from the snapshot
  });
});

describe("RegionSignal", () => {
  function signal(overrides: Partial<ReturnType<typeof useSignal>> = {}) {
    return {
      provider: "aws",
      region: "us-west-2",
      grid_zone: "US-NW-BPAT",
      intensity_gco2_kwh: 40,
      state: "green",
      advice: "run_now",
      cleaner_window_in_hours: null,
      cleaner_window_intensity_gco2_kwh: null,
      marginal_intensity_gco2_kwh: 80,
      marginal_note: null,
      marginal_basis: "heuristic",
      clean_surplus: true,
      surplus_window_in_hours: null,
      ...overrides,
      // biome-ignore lint/suspicious/noExplicitAny: partial signal fixture for the test
    } as any;
  }

  it("renders nothing when no precomputed signal exists", () => {
    mockUseSignal.mockReturnValue(undefined);
    const { container } = render(<RegionSignal provider="aws" region="us-west-2" />);
    expect(container.textContent).toBe("");
  });

  it("says run now for a clean-surplus region", () => {
    mockUseSignal.mockReturnValue(signal());
    render(<RegionSignal provider="aws" region="us-west-2" />);
    expect(screen.getByText(/Yes — run now/)).toBeTruthy();
  });

  it("says wait with the cleaner window when dirty", () => {
    mockUseSignal.mockReturnValue(
      signal({
        state: "red",
        advice: "wait_for_cleaner",
        clean_surplus: false,
        cleaner_window_in_hours: 5,
        cleaner_window_intensity_gco2_kwh: 120,
      }),
    );
    render(<RegionSignal provider="aws" region="us-west-2" />);
    expect(screen.getByText(/Wait ~5h for cleaner/)).toBeTruthy();
  });
});
