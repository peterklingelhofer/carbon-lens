import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 22 regions with strictly increasing intensity (r0 = cleanest), so the default
// "intensity ascending" sort and the 20-row cap are both observable.
const { snapshotFixture } = vi.hoisted(() => {
  const providers = ["aws", "gcp", "azure"];
  const regions = [];
  const intensities: Record<string, unknown> = {};
  const n = 22;
  for (let i = 0; i < n; i++) {
    const provider = providers[i % 3];
    const region = `r${i}`;
    regions.push({
      provider,
      region,
      grid_zone: `Z${i}`,
      location: `Loc ${i}`,
      latitude: 0,
      longitude: 0,
    });
    intensities[`${provider}/${region}`] = {
      grid_zone: `Z${i}`,
      carbon_intensity_gco2_kwh: (i + 1) * 10,
      renewable_percentage: 50,
      timestamp: "2026-06-14T00:00:00+00:00",
      source: "live",
      quality: "live",
    };
  }
  return {
    snapshotFixture: {
      generated_at: "2026-06-14T00:00:00+00:00",
      regions,
      intensities,
      summary: {
        live_zones: n,
        estimated_zones: 0,
        mock_zones_dropped: 0,
        regions_published: n,
        degraded: [],
      },
    },
  };
});

// snapshotEnabled=false so the LivePanel (WebSocket feed) renders; useSnapshot
// still returns the fixture so the table is deterministic.
vi.mock("../api/snapshot", () => ({
  snapshotEnabled: false,
  qualityFromSource: () => "live",
  dataBranchUrl: () => "",
  useSnapshot: () => ({ data: snapshotFixture }),
  // Derive-from-snapshot helpers used by the panels Dashboard renders (CustomZoneLookup,
  // RegionComparison). Stubbed empty -- this suite only asserts the regions table.
  gridZonesFromSnapshot: () => [],
  zoneIntensityFromSnapshot: () => undefined,
  greenestRegion: () => undefined,
}));

vi.mock("../api/client", () => ({
  api: {
    savings: vi.fn().mockResolvedValue({
      total_requests: 0,
      avg_intensity_reduction_gco2_kwh: 0,
      baseline: "mean carbon intensity of the candidate regions considered",
      avg_renewable_percentage: 0,
      records: [],
    }),
    regions: vi.fn(),
    route: vi.fn(),
    carbonIntensity: vi.fn(),
  },
}));

import { Dashboard } from "./Dashboard";

// Minimal WebSocket stand-in: jsdom has no WebSocket, and we want to drive
// open/message events by hand rather than over a real socket.
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {}
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderDashboard(): ReturnType<typeof render> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Dashboard />
    </QueryClientProvider>,
  );
}

describe("Dashboard table", () => {
  it("renders the snapshot regions and caps the table at 20", async () => {
    renderDashboard();
    expect(await screen.findByText("Loc 0")).toBeTruthy();
    expect(screen.getByText(/Showing 20 of 22/)).toBeTruthy();
    expect(screen.queryByText("Loc 21")).toBeNull(); // highest intensity, past the cap
  });

  it("sorts by carbon intensity ascending by default", async () => {
    renderDashboard();
    await screen.findByText("Loc 0");
    const rows = screen.getAllByRole("row");
    // rows[0] is the header; the first data row is the lowest intensity (Loc 0).
    expect(within(rows[1]).getByText("Loc 0")).toBeTruthy();
  });

  it("toggles to descending when the Carbon Intensity header is clicked", async () => {
    renderDashboard();
    await screen.findByText("Loc 0");
    fireEvent.click(screen.getByRole("button", { name: "Carbon Intensity" }));
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("Loc 21")).toBeTruthy(); // highest first now
    expect(screen.queryByText("Loc 0")).toBeNull(); // pushed past the cap
  });

  it("filters rows by the search box", async () => {
    renderDashboard();
    await screen.findByText("Loc 0");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search regions" }), {
      target: { value: "Loc 5" },
    });
    expect(screen.getByText("Loc 5")).toBeTruthy();
    expect(screen.queryByText("Loc 0")).toBeNull();
    expect(screen.queryByText(/Showing 20 of/)).toBeNull(); // single match, no cap note
  });

  it("filters by cloud provider", async () => {
    renderDashboard();
    await screen.findByText("Loc 0");
    fireEvent.click(screen.getByRole("button", { name: "aws" }));
    expect(screen.getByText("Loc 0")).toBeTruthy(); // aws (i=0)
    expect(screen.queryByText("Loc 1")).toBeNull(); // gcp (i=1) filtered out
  });
});

describe("Dashboard live feed", () => {
  it("connects over the WebSocket and renders pushed updates", async () => {
    renderDashboard();
    await screen.findByText("Loc 0");

    // LivePanel opened a socket but it hasn't connected yet.
    expect(screen.getByTitle("Disconnected")).toBeTruthy();
    const ws = MockWebSocket.instances.at(-1);
    expect(ws).toBeTruthy();

    act(() => ws?.onopen?.());
    expect(screen.getByTitle("Connected")).toBeTruthy();
    expect(ws?.sent[0]).toContain("interval_seconds"); // sent its subscription
    expect(screen.getByText("Waiting for first update...")).toBeTruthy();

    act(() =>
      ws?.onmessage?.({
        data: JSON.stringify({
          type: "carbon_update",
          timestamp: "t",
          data: [
            {
              provider: "aws",
              region: "us-east-1",
              grid_zone: "X",
              carbon_intensity_gco2_kwh: 100,
              renewable_percentage: 50,
              timestamp: "t",
              source: "live",
            },
          ],
        }),
      }),
    );
    expect(screen.queryByText("Waiting for first update...")).toBeNull();
    expect(screen.getByText("us-east-1")).toBeTruthy();
  });
});
