import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/report", () => ({
  REPORT_URL: "https://example/clean_compute_report.json",
  HISTORY_URL: "https://example/clean_compute_history.json",
  useCleanComputeReport: vi.fn(),
  useCleanComputeHistory: vi.fn(),
}));

import { useCleanComputeHistory, useCleanComputeReport } from "../api/report";
import { CleanCompute } from "./CleanCompute";

const mockHook = vi.mocked(useCleanComputeReport);
const mockHistory = vi.mocked(useCleanComputeHistory);

describe("CleanCompute", () => {
  it("renders the greenest regions and most-shiftable grids", () => {
    mockHook.mockReturnValue({
      data: {
        generated_at: "2026-06-17T12:00:00+00:00",
        days_analyzed: 14,
        greenest_regions: [
          {
            provider: "gcp",
            region: "europe-north1",
            location: "Finland",
            typical_gco2_kwh: 70,
            trend_pct: -8,
          },
        ],
        most_shiftable: [
          {
            grid_zone: "US-CAL-CISO",
            location: "California",
            shift_savings_pct: 62,
            cleanest_hour_utc: 13,
            samples: 120,
          },
        ],
      },
      isLoading: false,
      isError: false,
      // biome-ignore lint/suspicious/noExplicitAny: partial react-query result for the test
    } as any);
    mockHistory.mockReturnValue({
      data: {
        days: [
          { date: "2026-06-16", greenest_mean_gco2_kwh: 90, top_shiftability_pct: 60 },
          { date: "2026-06-17", greenest_mean_gco2_kwh: 80, top_shiftability_pct: 62 },
        ],
      },
      // biome-ignore lint/suspicious/noExplicitAny: partial react-query result for the test
    } as any);

    render(<CleanCompute />);
    expect(screen.getByText(/europe-north1/)).toBeTruthy();
    expect(screen.getByText("US-CAL-CISO")).toBeTruthy();
    expect(screen.getByText(/62% cleaner/)).toBeTruthy();
    expect(screen.getByText(/↓ 8%/)).toBeTruthy(); // greening trend indicator
    expect(screen.getByText("Trend")).toBeTruthy(); // multi-day trend section
  });
});
