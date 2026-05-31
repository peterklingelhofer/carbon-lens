# Kubernetes manifests — illustrative

These manifests show how CarbonLens *would* run on Kubernetes. They are
deployable demos, not a hardened production setup. Read this before relying on them.

## What's here and what works

- **`helm/carbon-mesh/`** — a real, `helm template`-able chart: Deployment, Service,
  Ingress, HPA (2–10 replicas @ 70% CPU), ConfigMap, and Secret templates with
  sane resource requests/limits. This is the part you can actually `helm install`.
- **`helmfile.yaml`** + **`environments/`** — three environments (default/staging/production)
  wiring the chart together with a Bitnami Postgres subchart.

## Known gaps (don't ship as-is)

- **The CRD is decorative.** `crd/carbon-route-policy.yaml` defines a
  `CarbonRoutePolicy` resource with a `status` subresource, but **there is no
  controller/operator** in this repo to reconcile it. You can `kubectl apply` the
  CRD and create resources, but nothing will act on them or populate `status`.
- **No migration Job.** The chart has no init-container or Job that runs
  `alembic upgrade head`, so a fresh deploy starts against an unmigrated database.
  (The Docker/PaaS paths handle this via `CARBON_MESH_AUTO_MIGRATE=true`.)
- **No pod-level `securityContext`.** Add `runAsNonRoot`/`readOnlyRootFilesystem`
  before any real deployment. (The container image itself already runs as a
  non-root `appuser`.)

For a quick, real deployment use Docker (`make up`), Render (`render.yaml`), or
Fly (`fly.toml`). The `k8s/` tree is here to demonstrate the shape of a production
rollout, not to be that rollout.
