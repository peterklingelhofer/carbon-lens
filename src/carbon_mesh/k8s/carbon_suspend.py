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
from datetime import datetime, timezone
from pathlib import Path

import httpx

from carbon_mesh.sdk import impact_from_signal

logger = logging.getLogger("carbon_suspend")

ANNOTATION_REGION = "carbonlens.dev/region"
ANNOTATION_MAX_INTENSITY = "carbonlens.dev/max-intensity"
# Deadline backstop: never let a job wait longer than this for a clean window.
ANNOTATION_MAX_DEFER = "carbonlens.dev/max-defer-hours"
_SA = "/var/run/secrets/kubernetes.io/serviceaccount"


def _ann_float(annotations: dict, key: str) -> float | None:
    raw = annotations.get(key)
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _hours_since(ts_iso: str | None, now: datetime) -> float | None:
    """Hours between an RFC3339 timestamp (e.g. a CronJob's lastScheduleTime) and now."""
    if not ts_iso:
        return None
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 3600


def overdue(hours_since_run: float | None, max_defer_hours: float | None) -> bool:
    """True when a job hasn't run within its max-defer window -- run it despite the grid."""
    return (
        max_defer_hours is not None
        and hours_since_run is not None
        and hours_since_run >= max_defer_hours
    )


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
    annotations: dict | None,
    current_suspend: bool | None,
    signal: dict,
    hours_since_run: float | None = None,
) -> bool | None:
    """The ``.spec.suspend`` a CronJob should have, or None if it's unmanaged or
    already correct (so we only patch when something actually changes).

    Honours a ``carbonlens.dev/max-defer-hours`` deadline: if the job hasn't run
    within that window, it's force-resumed even on a dirty grid -- so carbon-aware
    deferral never starves a job indefinitely.
    """
    ann = annotations or {}
    if not ann.get(ANNOTATION_REGION):
        return None
    cap = _ann_float(ann, ANNOTATION_MAX_INTENSITY)
    max_defer = _ann_float(ann, ANNOTATION_MAX_DEFER)
    want = should_suspend(signal, cap)
    if want and overdue(hours_since_run, max_defer):
        want = False  # deadline reached: run despite the grid
    return want if want != bool(current_suspend) else None


def report_on_suspend(region: str, want: bool, signal: dict) -> dict | None:
    """The impact entry to log when a CronJob is freshly suspended (deferred), or None.

    We report the *decision to defer* -- like the Celery/Prefect/Dagster integrations --
    using the signal's predicted reduction and its cleaner-window horizon. A resume
    (``want`` False) reports nothing: the run happens then, with no new deferral.
    """
    if not want:
        return None
    hours = signal.get("surplus_window_in_hours") or signal.get("cleaner_window_in_hours") or 0
    return impact_from_signal(region, signal, hours)


def _report_enabled() -> bool:
    return os.environ.get("CARBON_SUSPEND_REPORT", "").lower() in ("1", "true", "yes")


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

            # How long since this CronJob last fired (or was created if never), so the
            # deadline backstop can force it to run if it's been starved too long.
            last_run = item.get("status", {}).get("lastScheduleTime") or meta.get(
                "creationTimestamp"
            )
            hours_since = _hours_since(last_run, datetime.now(timezone.utc))

            current = item.get("spec", {}).get("suspend")
            want = desired_suspend_change(ann, current, signal, hours_since)
            if want is None:
                continue

            k8s.patch(
                f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}",
                json={"spec": {"suspend": want}},
                headers={"Content-Type": "application/merge-patch+json"},
            ).raise_for_status()
            changed += 1

            # Feed the org ledger on each fresh deferral (opt-in), so suspended CronJobs
            # accrue into org-statement like the other integrations. Best-effort.
            if _report_enabled() and (entry := report_on_suspend(region, want, signal)):
                try:
                    api.post("/api/v1/accounting/impact", json=entry).raise_for_status()
                except httpx.HTTPError as e:
                    logger.warning("impact report for %s failed (non-fatal): %s", name, e)
            logger.info(
                "%s/%s suspend=%s (region=%s, %s gCO2/kWh, surplus=%s, marginal=%s)",
                namespace,
                name,
                want,
                region,
                signal.get("intensity_gco2_kwh"),
                signal.get("clean_surplus"),
                signal.get("marginal_basis", "heuristic"),
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
