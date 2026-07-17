import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Minimal snapshot fixture. The aws/us-east-1 intensity entry carries the extra
// build-time-only fields (quality, carried_forward) that must NOT leak into a
// projected response; that's the whole point of the field projection.
const SNAPSHOT = {
  generated_at: "2026-07-16T12:00:00+00:00",
  regions: [
    { provider: "aws", region: "us-east-1", grid_zone: "US-MIDA-PJM", location: "Virginia" },
  ],
  intensities: {
    "aws/us-east-1": {
      grid_zone: "US-MIDA-PJM",
      carbon_intensity_gco2_kwh: 400.5,
      renewable_percentage: 20.1,
      timestamp: "2026-07-16T12:00:00+00:00",
      source: "eia",
      quality: "live",
      carried_forward: true,
      grid_load_mw: 1000,
      marginal_intensity_gco2_kwh: 500,
      power_breakdown_mw: { gas: 500 },
    },
  },
  signals: {},
  forecasts: {},
  weather: {},
  best_time: {
    "aws/us-east-1": {
      provider: "aws",
      region: "us-east-1",
      grid_zone: "US-MIDA-PJM",
      basis: "history",
      days_analyzed: 14,
      cleanest_hour_utc: 3,
      dirtiest_hour_utc: 18,
      shift_savings_pct: 40.2,
      annual_kg_saved: null,
      suggested_cron: "0 3 * * *",
      ranked_hours: [],
    },
  },
};

// Fresh module registry per test so the module-scope snapshot cache in
// worker.js never leaks between cases.
async function loadWorker() {
  vi.resetModules();
  return (await import("./worker.js")).default;
}

function envWith(overrides = {}) {
  return {
    SNAPSHOT_URL: "https://cdn.example/snapshot.json",
    ASSETS: { fetch: async () => new Response("spa", { status: 200 }) },
    ...overrides,
  };
}

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn(async (input) => {
    const url = typeof input === "string" ? input : input.url;
    if (url.startsWith("https://cdn.example/snapshot.json")) {
      return new Response(JSON.stringify(SNAPSHOT), { status: 200 });
    }
    // Anything else is the origin proxy fallthrough.
    return new Response("origin", { status: 200, headers: { "X-From": "origin" } });
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("worker.js snapshot read-through", () => {
  it("serves GET /api/v1/carbon/{provider}/{region} from the snapshot, projected", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/aws/us-east-1"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBe("snapshot");
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
    expect(res.headers.get("Content-Type")).toBe("application/json");

    const body = await res.json();
    expect(body).toEqual({
      grid_zone: "US-MIDA-PJM",
      carbon_intensity_gco2_kwh: 400.5,
      renewable_percentage: 20.1,
      timestamp: "2026-07-16T12:00:00+00:00",
      source: "eia",
      grid_load_mw: 1000,
      marginal_intensity_gco2_kwh: 500,
      power_breakdown_mw: { gas: 500 },
    });
    // The build-time-only fields must not leak into the API-shaped response.
    expect(body).not.toHaveProperty("quality");
    expect(body).not.toHaveProperty("carried_forward");
  });

  it("serves GET /api/v1/carbon/best-time/{provider}/{region} at default params", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/best-time/aws/us-east-1"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBe("snapshot");
    const body = await res.json();
    expect(body.cleanest_hour_utc).toBe(3);
    expect(body.days_analyzed).toBe(14);
  });

  it("falls through to origin when the snapshot has no entry for the key", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/aws/does-not-exist"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
  });

  it("falls through to origin when a response-affecting query param is present", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/best-time/aws/us-east-1?days=30"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
  });

  it("falls through to origin for non-GET requests", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/aws/us-east-1", { method: "POST" }),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
    // Never even attempted the snapshot fetch for a non-GET request.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0].url ?? fetchMock.mock.calls[0][0]).not.toContain(
      "snapshot.json",
    );
  });

  it("falls through to origin when the snapshot fetch fails", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.startsWith("https://cdn.example/snapshot.json")) {
        return new Response("boom", { status: 500 });
      }
      return new Response("origin", { status: 200 });
    });
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/aws/us-east-1"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
  });

  it("does not intercept GET /api/v1/regions (proxied; see worker.js note)", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(new Request("https://example.com/api/v1/regions"), envWith());
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
  });

  it("does not intercept GET /api/v1/carbon/forecast/{provider}/{region} (proxied; see worker.js note)", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(
      new Request("https://example.com/api/v1/carbon/forecast/aws/us-east-1"),
      envWith(),
    );
    expect(res.headers.get("X-Carbon-Lens-Source")).toBeNull();
    expect(await res.text()).toBe("origin");
  });

  it("passes non-API paths straight to env.ASSETS", async () => {
    const worker = await loadWorker();
    const res = await worker.fetch(new Request("https://example.com/globe"), envWith());
    expect(await res.text()).toBe("spa");
  });
});
