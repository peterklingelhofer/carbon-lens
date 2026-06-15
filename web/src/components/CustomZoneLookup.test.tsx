import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CarbonIntensity, GridZoneSummary } from "../api/types";
import { CustomZoneLookup } from "./CustomZoneLookup";

vi.mock("../api/client", () => ({
  api: { carbonZones: vi.fn(), carbonZone: vi.fn() },
}));

import { api } from "../api/client";

const mockZones = vi.mocked(api.carbonZones);
const mockZone = vi.mocked(api.carbonZone);

afterEach(() => vi.clearAllMocks());

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const zones: GridZoneSummary[] = [
  { grid_zone: "DE", location: "Germany", regions: ["aws/eu-central-1", "ovh/fra"] },
  { grid_zone: "FR", location: "France", regions: ["scaleway/fr-par"] },
];

function intensity(zone: string, value: number): CarbonIntensity {
  return {
    grid_zone: zone,
    carbon_intensity_gco2_kwh: value,
    renewable_percentage: 55,
    timestamp: "2026-06-15T00:00:00Z",
    source: "test",
  };
}

describe("CustomZoneLookup", () => {
  it("shows the selected zone's intensity and the cloud regions on that grid", async () => {
    mockZones.mockResolvedValue(zones);
    mockZone.mockResolvedValue(intensity("DE", 180));

    renderWithClient(<CustomZoneLookup />);

    expect(await screen.findByText("180")).toBeTruthy();
    expect(screen.getByText("55% renewable")).toBeTruthy();
    expect(screen.getByText(/aws\/eu-central-1/)).toBeTruthy();
    expect(mockZone).toHaveBeenCalledWith("DE");
  });
});
