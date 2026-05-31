"""Spot / preemptible GPU price feeds for the ZK broker demo.

DEMO DATA: these are representative, hand-maintained price points, not a live
feed. A production build would wire these methods to real sources (AWS EC2 Spot
Price History API, GCP pricing tables, alt-cloud pricing pages); the interface
and cache are real so that swap is a drop-in. Prices are illustrative only.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from carbon_mesh.models.zk import (
    ComputeProvider,
    GPUType,
    SpotPriceQuote,
)

# Cache TTL for spot prices (5 minutes)
_CACHE_TTL_SECONDS = 300


class SpotPriceFeed:
    """Aggregates representative GPU spot prices from all providers (demo data)."""

    def __init__(self) -> None:
        self._cache: dict[str, SpotPriceQuote] = {}
        self._cache_time: float = 0.0

    async def get_prices(self, gpu_type: GPUType | None = None) -> list[SpotPriceQuote]:
        """Get current GPU spot prices from all sources.

        Returns cached results if within TTL, otherwise fetches fresh data.
        """
        now = time.monotonic()
        if now - self._cache_time > _CACHE_TTL_SECONDS or not self._cache:
            await self._refresh_all()
            self._cache_time = now

        quotes = list(self._cache.values())
        if gpu_type:
            quotes = [q for q in quotes if q.gpu_type == gpu_type]
        return sorted(quotes, key=lambda q: q.price_per_hour_usd)

    async def get_price(
        self, provider: ComputeProvider, region: str, gpu_type: GPUType
    ) -> SpotPriceQuote | None:
        """Get a specific price quote."""
        quotes = await self.get_prices(gpu_type)
        for q in quotes:
            if q.provider == provider and q.region == region:
                return q
        return None

    async def _refresh_all(self) -> None:
        """Rebuild the price table from the demo price sets.

        In a production build each of these would fetch from a real source;
        here they return representative static prices.
        """
        quotes: list[SpotPriceQuote] = [
            *self._green_datacenter_prices(),
            *self._aws_prices(),
            *self._gcp_prices(),
            *self._alt_cloud_prices(),
        ]

        # Update cache
        self._cache = {f"{q.provider.value}:{q.region}:{q.gpu_type.value}": q for q in quotes}

    @staticmethod
    def _green_datacenter_prices() -> list[SpotPriceQuote]:
        """Fixed contract rates from green compute partners.

        These are negotiated rates for behind-the-meter renewable facilities.
        Updated when contracts are renegotiated (typically quarterly).
        """
        now = datetime.now(timezone.utc)
        return [
            SpotPriceQuote(
                provider=ComputeProvider.IREN,
                region="ca-bc-1",
                gpu_type=GPUType.RTX_4090,
                price_per_hour_usd=0.65,
                available=True,
                interruption_rate_pct=0.0,  # Dedicated, no interruption
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.TERAWULF,
                region="us-ny-lm",
                gpu_type=GPUType.RTX_4090,
                price_per_hour_usd=0.70,
                available=True,
                interruption_rate_pct=0.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.HIVE_DIGITAL,
                region="is-reykjavik",
                gpu_type=GPUType.A100_40GB,
                price_per_hour_usd=0.90,
                available=True,
                interruption_rate_pct=0.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.HIVE_DIGITAL,
                region="se-stockholm",
                gpu_type=GPUType.RTX_4090,
                price_per_hour_usd=0.60,
                available=True,
                interruption_rate_pct=0.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.BITDEER,
                region="no-oslo",
                gpu_type=GPUType.A100_80GB,
                price_per_hour_usd=1.00,
                available=True,
                interruption_rate_pct=0.0,
                fetched_at=now,
            ),
        ]

    @staticmethod
    def _aws_prices() -> list[SpotPriceQuote]:
        """Representative AWS EC2 Spot GPU prices (demo data).

        Production would parse the EC2 Spot Price History API here.
        """
        now = datetime.now(timezone.utc)
        return [
            SpotPriceQuote(
                provider=ComputeProvider.AWS_SPOT,
                region="us-east-1",
                gpu_type=GPUType.A100_40GB,
                price_per_hour_usd=1.10,
                available=True,
                interruption_rate_pct=5.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.AWS_SPOT,
                region="eu-west-1",
                gpu_type=GPUType.A100_40GB,
                price_per_hour_usd=1.25,
                available=True,
                interruption_rate_pct=3.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.AWS_SPOT,
                region="us-east-1",
                gpu_type=GPUType.T4,
                price_per_hour_usd=0.15,
                available=True,
                interruption_rate_pct=8.0,
                fetched_at=now,
            ),
        ]

    @staticmethod
    def _gcp_prices() -> list[SpotPriceQuote]:
        """Representative GCP preemptible GPU prices (demo data)."""
        now = datetime.now(timezone.utc)
        return [
            SpotPriceQuote(
                provider=ComputeProvider.GCP_PREEMPTIBLE,
                region="us-central1",
                gpu_type=GPUType.T4,
                price_per_hour_usd=0.35,
                available=True,
                interruption_rate_pct=10.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.GCP_PREEMPTIBLE,
                region="europe-west4",
                gpu_type=GPUType.A100_80GB,
                price_per_hour_usd=1.85,
                available=True,
                interruption_rate_pct=5.0,
                fetched_at=now,
            ),
        ]

    @staticmethod
    def _alt_cloud_prices() -> list[SpotPriceQuote]:
        """Published pricing from alt-cloud GPU providers."""
        now = datetime.now(timezone.utc)
        return [
            SpotPriceQuote(
                provider=ComputeProvider.COREWEAVE,
                region="us-lga-1",
                gpu_type=GPUType.H100,
                price_per_hour_usd=2.49,
                available=True,
                interruption_rate_pct=0.0,  # On-demand, no interruption
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.LAMBDA_LABS,
                region="us-tx-1",
                gpu_type=GPUType.A100_80GB,
                price_per_hour_usd=1.29,
                available=True,
                interruption_rate_pct=0.0,
                fetched_at=now,
            ),
            SpotPriceQuote(
                provider=ComputeProvider.VAST_AI,
                region="global",
                gpu_type=GPUType.RTX_4090,
                price_per_hour_usd=0.40,
                available=True,
                interruption_rate_pct=15.0,  # Community GPUs can go offline
                fetched_at=now,
            ),
        ]

    async def close(self) -> None:
        """No-op — kept for interface compatibility (demo data needs no client)."""
        return None
