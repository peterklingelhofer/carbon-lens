# Carbon-aware autoscaling with KEDA

Scale a flexible **Deployment** (a queue consumer, batch worker, render farm,
training fleet) to zero except when the grid is in **clean surplus** — so the work
runs on power that would otherwise be curtailed. Declarative, with infrastructure
many clusters already run (KEDA + Prometheus); no app changes.

This pairs with the `carbon_clean_surplus` Prometheus gauge CarbonLens exposes on
`/metrics` (1 during clean surplus, 0 otherwise). Where the CronJob controller in
`../carbon-suspend` handles scheduled jobs, this handles always-defined Deployments.

## Prerequisites

- [KEDA](https://keda.sh) installed in the cluster
- Prometheus scraping a CarbonLens `/metrics` endpoint (so `carbon_clean_surplus` exists)
- A Deployment of **interruptible** workers (they may be scaled to 0 at any time)

## Install

```bash
# Edit the grid zone, Deployment name, and Prometheus address first.
kubectl apply -f deploy/k8s/keda/scaledobject.yaml
```

## How it works

`carbon_clean_surplus{grid_zone="…"}` is `1` only when renewables are abundant and
the margin is clean. With `threshold: "1"` and `activationThreshold: "0.5"`, KEDA
keeps the Deployment at `minReplicaCount` (0) until the metric crosses 0.5 — i.e.
hits 1 — then scales up toward `maxReplicaCount`. When surplus ends, it scales back
to 0 after `cooldownPeriod`.

## Graded scaling (capture the yellow middle)

On/off surplus scaling leaves savings on the table during the large "yellow" period
when the grid is neither clean surplus nor dirty. [`graded-scaledobject.yaml`](graded-scaledobject.yaml)
scales **in proportion** to the `carbon_intensity_tier` gauge (0 green, 1 yellow, 2
red): the fleet runs largest when green, smaller on yellow, and down to a floor when
red. Use it for work that's flexible in *volume* (it can run partially) rather than
strictly all-or-nothing.

## Honest limits

- Only for **interruptible, queue-style** work: replicas can vanish at any time, so
  workers must checkpoint / be safe to kill mid-task.
- Clean surplus is intermittent and not guaranteed daily in every zone — pair with a
  deadline (e.g. a CronJob that force-runs the backlog if surplus hasn't occurred in
  N hours) for work that can't wait indefinitely.
- Surplus is a heuristic (renewable-share + low carbon + clean margin), not metered
  curtailment. It's a strong, conservative signal, not a guarantee of zero marginal.
