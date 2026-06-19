# Carbon-aware CronJob suspend controller

Toggle your Kubernetes `CronJob`s on and off by the live grid — run flexible,
idempotent batch work (backups, ETL, reports, housekeeping) when the electricity is
cleanest, with **no change to the workloads themselves**.

The controller runs as a `CronJob`, lists annotated CronJobs in its namespace, asks
CarbonLens whether now is a good time for each one's region, and patches
`.spec.suspend` accordingly — using the same marginal/clean-surplus intelligence as
the rest of the tool.

## Opt a CronJob in

Add annotations to any CronJob you want managed:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-backup
  annotations:
    carbonlens.dev/region: aws/us-east-1      # or zone/FR for an on-prem grid zone
    carbonlens.dev/max-intensity: "150"       # optional gCO2/kWh cap
    carbonlens.dev/max-defer-hours: "12"      # optional deadline: run anyway if starved this long
spec:
  schedule: "0 * * * *"
  # ... your job ...
```

A managed CronJob is **suspended** when its grid is a dirty time to run, and
**resumed** when the signal says `run_now` or it's clean surplus (within your cap).
With `carbonlens.dev/max-defer-hours`, a job that hasn't fired within that window is
force-resumed even on a dirty grid — so carbon-aware deferral **never starves a job
indefinitely** (the deadline measures from the CronJob's last schedule time).

## Install

```bash
kubectl apply -f deploy/k8s/carbon-suspend/rbac.yaml
kubectl apply -f deploy/k8s/carbon-suspend/cronjob.yaml   # set image: + namespace
```

The controller needs only `get`/`list`/`patch` on `cronjobs` in its namespace (see
`rbac.yaml`). It reaches the cluster through its in-cluster service-account token —
no extra dependencies. Point `CARBONLENS_API_URL` at your own deployment if you run
one; otherwise it uses the public instance.

Set `CARBON_SUSPEND_REPORT=true` to post each fresh deferral's predicted impact to the
API's org ledger (`/accounting/impact`), so suspended CronJobs accrue into
`org-statement` and the Prometheus impact gauges like the Celery/Prefect/Dagster
integrations and `carbonlens run --report-to`. Best-effort — a reporting failure never
affects suspend/resume.

## Honest limits

- A suspended `CronJob` **skips** fire times while suspended; it does **not** queue
  and catch up. Only manage jobs where skipping until a cleaner window is fine.
- Shifting helps when the grid is genuinely variable and the work is flexible. The
  controller honours the signal's honesty: if the margin is fossil either way it
  won't suspend pointlessly, and clean-surplus windows keep jobs running.
- Decision interval is the controller's own schedule (default every 20 min), so
  suspend/resume is coarse-grained — appropriate for hourly/daily jobs, not minutely.
