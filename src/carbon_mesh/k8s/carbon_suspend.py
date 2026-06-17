"""Carbon-aware Kubernetes CronJob controller.

Suspends and resumes annotated CronJobs by the live grid: a job's ``.spec.suspend``
is set true when its region is a dirty time to run and false when it's a good time
(``run_now`` or clean surplus). Opt in per CronJob with annotations -- no app or
image changes to the workload itself:

    metadata:
      annotations:
        carbonlens.dev/region: aws/us-east-1     # or zone/FR for on-prem grids
        carbonlens.dev/max-intensity: "150"      # optional gCO2/kWh cap

Run it as a CronJob itself every ~20 min (see deploy/k8s/carbon-suspend). It talks
to the cluster via the in-cluster service-account token over httpx -- no kubernetes
client dependency. The decision logic is pure and unit-tested.

Honest limits: this shifts genuinely flexible, idempotent CronJobs (backups,
batch ETL, report generation, housekeeping). A suspended CronJob simply skips
fire times while suspended -- it does not queue and catch up -- so only use it
where skipping until a cleaner window is acceptable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger("carbon_suspend")

ANNOTATION_REGION = "carbonlens.dev/region"
ANNOTATION_MAX_INTENSITY = "carbonlens.dev/max-intensity"
_SA = "/var/run/secrets/kubernetes.io/serviceaccount"


def should_suspend(signal: dict, max_intensity: float | None = None) -> bool:
    """True when a flexible job should be suspended (now is not a good time to run).

    A good time = the signal says ``run_now`` or it's clean surplus, and -- if the
    caller set a cap -- intensity is at/under it.
    """
    clean = signal.get("advice") == "run_now" or signal.get("clean_surplus") is True
    if max_intensity is not None and (signal.get("intensity_gco2_kwh") or 0) > max_intensity:
        clean = False
    return not clean


def desired_suspend_change(
    annotations: dict | None, current_suspend: bool | None, signal: dict
) -> bool | None:
    """The ``.spec.suspend`` a CronJob should have, or None if it's unmanaged or
    already correct (so we only patch when something actually changes)."""
    ann = annotations or {}
    if not ann.get(ANNOTATION_REGION):
        return None
    raw_cap = ann.get(ANNOTATION_MAX_INTENSITY)
    try:
        cap = float(raw_cap) if raw_cap is not None else None
    except (TypeError, ValueError):
        cap = None
    want = should_suspend(signal, cap)
    return want if want != bool(current_suspend) else None


def _signal_path(region: str) -> str:
    """API path for a region annotation. ``zone/FR`` -> the on-prem zone endpoint,
    ``aws/us-east-1`` -> the cloud-region endpoint (partition handles both)."""
    provider, _, reg = region.partition("/")
    return f"/api/v1/carbon/signal/{provider}/{reg}"


def _api_url() -> str:
    return os.environ.get("CARBONLENS_API_URL", "https://carbonlens-gssa.onrender.com").rstrip("/")


def reconcile() -> int:
    """List annotated CronJobs in the namespace and patch suspend by the grid.

    Returns the number of CronJobs actually changed. Reads the in-cluster
    service-account credentials; raises FileNotFoundError when not run in a cluster.
    """
    token = Path(f"{_SA}/token").read_text().strip()
    namespace = (
        os.environ.get("CARBON_SUSPEND_NAMESPACE") or Path(f"{_SA}/namespace").read_text().strip()
    )

    api = httpx.Client(base_url=_api_url(), timeout=20)
    k8s = httpx.Client(
        base_url="https://kubernetes.default.svc",
        headers={"Authorization": f"Bearer {token}"},
        verify=f"{_SA}/ca.crt",
        timeout=20,
    )
    changed = 0
    signals: dict[str, dict] = {}
    try:
        resp = k8s.get(f"/apis/batch/v1/namespaces/{namespace}/cronjobs")
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            meta = item.get("metadata", {})
            ann = meta.get("annotations", {}) or {}
            region = ann.get(ANNOTATION_REGION)
            if not region:
                continue
            name = meta.get("name", "?")

            if region not in signals:
                try:
                    sig = api.get(_signal_path(region))
                    sig.raise_for_status()
                    signals[region] = sig.json()
                except httpx.HTTPError as e:
                    logger.warning("skip %s: signal for %s unavailable (%s)", name, region, e)
                    continue
            signal = signals[region]

            current = item.get("spec", {}).get("suspend")
            want = desired_suspend_change(ann, current, signal)
            if want is None:
                continue

            k8s.patch(
                f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}",
                json={"spec": {"suspend": want}},
                headers={"Content-Type": "application/merge-patch+json"},
            ).raise_for_status()
            changed += 1
            logger.info(
                "%s/%s suspend=%s (region=%s, %s gCO2/kWh, surplus=%s)",
                namespace,
                name,
                want,
                region,
                signal.get("intensity_gco2_kwh"),
                signal.get("clean_surplus"),
            )
    finally:
        k8s.close()
        api.close()
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        n = reconcile()
        logger.info("carbon-suspend: %d CronJob(s) updated", n)
    except FileNotFoundError:
        logger.error(
            "Not running in-cluster (no service-account token). Deploy as a Kubernetes "
            "CronJob -- see deploy/k8s/carbon-suspend."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
