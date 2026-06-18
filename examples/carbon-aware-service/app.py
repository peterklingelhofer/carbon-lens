"""A copy-paste carbon-aware FastAPI service.

Shows the two always-on patterns end to end:

1. ``CarbonAwareShedder`` middleware tags every response with ``X-Carbon-Mode`` and
   sheds requests the caller marked optional (``X-Carbon-Optional: 1``) when the grid
   is dirty.
2. Handlers degrade quality by the grid with ``choose_by_state`` -- a leaner AI model
   and lower media bitrate on yellow/red, full quality on green.

Run it:

    uv run uvicorn examples.carbon-aware-service.app:app --reload
    curl -i localhost:8000/infer                       # see X-Carbon-Mode header
    curl -i -H 'X-Carbon-Optional: 1' localhost:8000/recommendations

Point ``REGION`` at where your service runs (or a zone/<id> for on-prem). By default
it uses the public CarbonLens instance; set ``api_url=`` for your own deployment.
"""

from fastapi import FastAPI

from carbon_mesh.middleware import CarbonAwareShedder
from carbon_mesh.sdk import CarbonClient, choose_by_state

REGION = "aws/us-east-1"
_client = CarbonClient()

app = FastAPI(title="Carbon-aware service example")

# Tag responses with the grid mode, and shed explicitly-optional requests when dirty.
app.add_middleware(CarbonAwareShedder, region=REGION, max_intensity=400, shed_optional=True)


@app.get("/infer")
def infer() -> dict:
    """Serve a leaner model when the grid is dirtier (graded by the traffic light)."""
    model = choose_by_state(
        _client.signal(REGION), green="gpt-full", yellow="gpt-mid", red="gpt-mini"
    )
    return {"model": model, "note": "model tier chosen by current grid carbon"}


@app.get("/media")
def media() -> dict:
    """Pick a bitrate by the grid -- the same degradation a client could do itself."""
    bitrate = choose_by_state(_client.signal(REGION), green="1080p", yellow="720p", red="480p")
    return {"bitrate": bitrate}


@app.get("/recommendations")
def recommendations() -> dict:
    """Non-essential work. Callers send ``X-Carbon-Optional: 1`` and the middleware
    sheds it with a 503 + Retry-After while the grid is dirty; otherwise it runs."""
    return {"items": ["a", "b", "c"]}
