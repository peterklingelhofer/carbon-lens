# Carbon-aware service example

A minimal FastAPI service showing how an **always-on** app becomes carbon-aware
without deferring anything — it does *less* when the grid is dirty.

```bash
uv run uvicorn examples.carbon-aware-service.app:app --reload
```

```bash
curl -i localhost:8000/infer
#   X-Carbon-Mode: full|reduced
#   X-Carbon-Intensity: <gCO2/kWh>
#   {"model": "gpt-full" | "gpt-mid" | "gpt-mini"}   # leaner model when dirtier

curl -i -H 'X-Carbon-Optional: 1' localhost:8000/recommendations
#   200 when clean; 503 + Retry-After when the grid is dirty (shed)
```

## What it wires together

- **`CarbonAwareShedder`** (`carbon_mesh.middleware`) tags every response with the
  grid mode and sheds optional requests when dirty.
- **`choose_by_state`** (`carbon_mesh.sdk`) picks model tier / bitrate by the
  traffic-light state (green/yellow/red).
- A browser client can read the same headers with
  [`readCarbonHeaders`](../../web/src/lib/carbonMode.ts) and degrade on its side too.

## Honest limits

Only degrade *non-essential* quality/work — never correctness. Set `max_intensity`
and the tiers to match what your users will accept. Point `api_url` at your own
CarbonLens deployment for production rather than the public demo instance.
