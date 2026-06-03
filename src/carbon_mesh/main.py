import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from prometheus_fastapi_instrumentator import Instrumentator

from carbon_mesh.api.routes import router
from carbon_mesh.api.ws import ws_router
from carbon_mesh.config import settings
from carbon_mesh.compliance.routes import router as compliance_router
from carbon_mesh.scheduler.routes import router as scheduler_router
from carbon_mesh.sla.routes import router as sla_router

from carbon_mesh.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("carbon_mesh")

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])


async def _warmup_cache() -> None:
    """Pre-fetch carbon intensity for popular zones so first requests are instant."""
    from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
    from carbon_mesh.api.ws import DEFAULT_REGIONS

    source = get_carbon_source()
    mapper = get_grid_mapper()

    zones: list[str] = []
    for r in DEFAULT_REGIONS:
        try:
            zone = mapper.get_grid_zone(r["provider"], r["region"])
            if zone and zone not in zones:
                zones.append(zone)
        except Exception:
            pass

    if not zones:
        return

    try:
        results = await source.get_carbon_intensity_batch(zones)
        logger.info("Cache warmup: pre-fetched %d/%d popular zones", len(results), len(zones))
    except Exception as e:
        logger.warning("Cache warmup failed (non-fatal): %s", e)


def _log_provider_status() -> None:
    """Log which carbon data providers are configured at startup."""
    providers = settings.configured_providers
    configured = [name for name, ok in providers.items() if ok]
    missing = [name for name, ok in providers.items() if not ok]
    logger.info(
        "Carbon data providers ready (%d/%d): %s",
        len(configured),
        len(providers),
        ", ".join(configured),
    )
    if missing:
        logger.warning(
            "Providers missing credentials (%d): %s — add API keys to .env for live data",
            len(missing),
            ", ".join(missing),
        )


def _check_security_posture() -> None:
    """Warn loudly about insecure config and reject the unsafe wildcard-CORS combination."""
    if not settings.api_key_required:
        logger.warning(
            "CARBON_LENS_API_KEY_REQUIRED=false — running in OPEN demo mode with no authentication. "
            "Set it to true for any non-demo deployment."
        )
    if "*" in settings.cors_origins:
        raise RuntimeError(
            "CORS origins include '*'. Wildcard origins are not allowed — "
            "set CARBON_LENS_CORS_ORIGINS to an explicit allowlist."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    import signal

    shutdown_event = asyncio.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        logger.info("Received %s — starting graceful shutdown", signal.Signals(sig).name)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handle_signal)

    app.state.shutdown_event = shutdown_event

    _check_security_posture()
    _log_provider_status()

    if settings.use_database:
        # Auto-run Alembic migrations if configured (great for PaaS deploys)
        if settings.auto_migrate:
            import subprocess

            logger.info("Running database migrations (AUTO_MIGRATE=true)...")
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Migrations complete.")
            else:
                logger.error("Migration failed: %s", result.stderr)

        from carbon_mesh.db.engine import async_engine
        from carbon_mesh.db.init_db import create_tables

        # Retry DB connection (PaaS databases can be slow to start)
        for attempt in range(1, 6):
            try:
                logger.info("Connecting to database (attempt %d/5)...", attempt)
                await create_tables()
                logger.info("Database ready.")
                break
            except Exception as e:
                if attempt == 5:
                    logger.error("Database connection failed after 5 attempts: %s", e)
                    raise
                logger.warning("Database not ready, retrying in %ds: %s", attempt * 2, e)
                await asyncio.sleep(attempt * 2)

        await _warmup_cache()
        yield
        await async_engine.dispose()
        logger.info("Database connection closed.")
    else:
        logger.info("Running without database (in-memory mode).")
        await _warmup_cache()
        yield


app = FastAPI(
    title="CarbonLens",
    description=(
        "A free, open API for the real-time carbon intensity of cloud regions. "
        "No account or API key required; usage is rate-limited so it stays "
        "responsive for everyone.\n\n"
        "## Carbon Data API\n"
        "- **6 live grid-operator integrations** (UK, EIA, AEMO, GridStatus, ENTSO-E, "
        "Electricity Maps) plus labeled heuristic and weather-based estimates, cascading\n"
        "- **Grid carbon intensity** for 75+ cloud regions; every response is tagged with its `source`\n"
        "- **Batch queries** for multiple regions in a single call\n\n"
        "## Compliance Reporting\n"
        "- **GHG-Protocol-structured** Scope 2 (location-based) + Scope 3 Cat 1 reporting\n"
        "- Drafts aimed at **CSRD / SEC Climate / SB 253** workflows (not an assured report)\n"
        "- **EU Taxonomy** eligibility flag (simplified screening)\n\n"
        "## Green SLA Monitoring (Beta)\n"
        "- **Define carbon targets** — max gCO2/kWh, min renewable %\n"
        "- **On-demand + background checks** (in-memory state)\n"
        "- **Attestation-style summary reports**\n\n"
        "## Carbon-Aware Scheduling\n"
        "- **Find optimal time windows** for batch jobs, CI/CD, ML training\n"
        "- **Multi-region evaluation** across AWS, GCP, Azure\n"
        "- **Three strategies** — lowest carbon, highest renewable, balanced\n"
        "- Returns a recommendation — it doesn't run or defer your workload itself"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Routing", "description": "Find the greenest cloud region for your workload"},
        {
            "name": "Regions",
            "description": "Explore supported cloud regions across AWS, GCP, and Azure",
        },
        {
            "name": "Carbon Data",
            "description": "Get real-time carbon intensity for specific regions",
        },
        {
            "name": "Scheduling",
            "description": "Carbon-aware scheduling — find optimal low-carbon time windows for batch jobs",
        },
        {
            "name": "SLA Monitoring",
            "description": "Green SLA definitions, compliance checks, attestation reports, and alerts",
        },
        {
            "name": "Compliance",
            "description": "CSRD/SEC/SB-253 emissions measurement, calculation, and reporting",
        },
        {"name": "Accounting", "description": "Track carbon savings from routed workloads"},
        {"name": "System", "description": "Health checks and operational endpoints"},
    ],
)

# GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS — configurable origins, locked down in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    """Reject oversized request bodies early (before parsing)."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_body_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "error": "request_too_large",
                "detail": f"Request body exceeds {settings.max_request_body_bytes} bytes.",
            },
        )
    return await call_next(request)


@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "%s %s %d %.1fms req=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    response.headers["X-Request-ID"] = request_id

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "bad_request",
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


app.state.limiter = limiter
# Enforce the default rate limit (settings.rate_limit_default) on every route
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": f"Rate limit exceeded: {exc.detail}",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


app.include_router(router, prefix="/api/v1", tags=["Carbon Routing"])
app.include_router(compliance_router)
app.include_router(scheduler_router)
app.include_router(sla_router)
app.include_router(ws_router)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


async def _check_db() -> str | None:
    """Check database connectivity. Returns None if OK, error string if not."""
    if not settings.use_database:
        return None
    try:
        from sqlalchemy import text

        from carbon_mesh.db.engine import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return None
    except Exception as e:
        return str(e)


@app.get("/health", tags=["System"])
async def health() -> dict:
    db_error = await _check_db()
    result = {
        "status": "ok",
        "version": "0.1.0",
        "carbon_source": settings.carbon_source,
        "database": "disabled"
        if not settings.use_database
        else ("connected" if db_error is None else "unreachable"),
    }
    if db_error is not None:
        result["status"] = "degraded"
    return result


@app.get("/ready", tags=["System"])
async def readiness() -> dict:
    """Readiness probe — returns 200 only when all dependencies are available.

    Use this for Kubernetes readinessProbe or load balancer health checks.
    Unlike /health (liveness), this will return 503 if the database is unreachable.
    """
    db_error = await _check_db()
    if db_error is not None:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "database unreachable"},
        )
    return {"status": "ready"}


@app.get("/health/providers", tags=["System"])
async def provider_status() -> dict:
    """Show which carbon data providers are configured and ready.

    Use this to verify your API keys are set correctly after deployment.
    """
    providers = settings.configured_providers
    return {
        "configured": {k: v for k, v in providers.items() if v},
        "missing": {k: v for k, v in providers.items() if not v},
        "total_configured": sum(1 for v in providers.values() if v),
        "total_available": len(providers),
    }


def run() -> None:
    uvicorn.run(
        "carbon_mesh.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
