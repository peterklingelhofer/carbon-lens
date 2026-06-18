# Carbon-aware Argo Workflows

Gate flexible **Argo Workflows** work on the grid: a reusable `carbon-gate` step asks
CarbonLens whether the region is a good time to run and prints `clean`/`dirty`, which
your workflow branches on with a `when:`. Argo Workflows runs a huge share of k8s-native
ML/data batch — this makes it carbon-aware with no change to the work itself.

## Install

```bash
kubectl apply -f deploy/argo/carbon-gate-template.yaml       # reusable gate
kubectl apply -f deploy/argo/carbon-aware-cronworkflow.yaml  # example
```

## Use the gate in your own workflow

```yaml
steps:
  - - name: gate
      templateRef: { name: carbon-gate, template: gate }
      arguments:
        parameters:
          - { name: region, value: "aws/us-east-1" }   # or zone/FR on-prem
          - { name: max-intensity, value: "150" }
  - - name: train
      when: "'{{steps.gate.outputs.result}}' == 'clean'"
      template: train-model
```

The gate reuses `carbon_mesh.sdk` (the same marginal/clean-surplus decision as the
CLI, Action, Kubernetes, Airflow, Prefect, Dagster, and Celery surfaces), so it needs
an image with `carbon_mesh` installed — the API image works, or your own.

## Pattern & honest limits

- The example is a **CronWorkflow**: it re-evaluates every 30 min and runs the work
  only on clean ticks. That's a skip-and-retry — it never blocks a worker and never
  fails just for being dirty. Pick a `schedule` that gives enough chances within your
  deadline.
- For a one-shot Workflow, gate the same way; if it's dirty it simply skips. Add your
  own deadline logic (e.g. a final unconditional run) if the work must complete by a
  time.
- Only gate genuinely flexible, idempotent work. Point `api-url` at your own
  deployment for production.
