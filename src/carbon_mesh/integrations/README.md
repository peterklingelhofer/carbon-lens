# Framework integrations

## Apache Airflow — `CarbonAwareSensor`

A **deferrable** sensor that gates a downstream task on the grid: it succeeds only
once the region is a good time to run, and because it's deferrable it **frees the
worker slot while waiting** (the poll runs in the triggerer). That's the correct way
to make a DAG carbon-aware — a blocking call would hold a worker for hours.

```python
from carbon_mesh.integrations.airflow import CarbonAwareSensor

wait_for_clean = CarbonAwareSensor(
    task_id="wait_for_clean_grid",
    region="aws/us-east-1",      # or zone/FR for on-prem grids
    max_intensity=150,           # optional gCO2/kWh cap
    max_wait_hours=6,            # deadline backstop: proceed anyway after this
)

wait_for_clean >> train_model    # train_model runs once the grid is clean
```

The sensor defers to `CarbonCleanTrigger`, which polls `/carbon/signal` until the
grid says `run_now` / clean surplus (within your cap) or the deadline passes — so a
DAG is never blocked forever. It uses the same decision as every other surface
(`carbon_mesh.sdk.is_good_time`).

`apache-airflow` is an optional dependency: `pip install apache-airflow`. The module
imports without it; only instantiating the sensor requires it.

### Honest limits

Only gate genuinely flexible tasks (nightly batch, retraining, report generation).
Set `max_wait_hours` so time-sensitive DAGs still complete. `api_url` defaults to the
public instance — point it at your own deployment for production.

## Prefect — `wait_for_clean_window`

```python
from prefect import flow
from carbon_mesh.integrations.prefect import wait_for_clean_window

@flow
def nightly():
    wait_for_clean_window("aws/us-east-1", max_intensity=150, max_wait_hours=6)
    train_model()
```

`clean_window_task(**task_kwargs)` returns it as a native Prefect `@task`. `pip install prefect`.

## Dagster — `clean_window_op`

```python
from dagster import job
from carbon_mesh.integrations.dagster import clean_window_op

wait = clean_window_op("aws/us-east-1", max_intensity=150, max_wait_hours=6)

@job
def nightly():
    train_model(wait())
```

`pip install dagster`. Both reuse `carbon_mesh.sdk`, so the decision matches the CLI,
GitHub Action, Kubernetes, and Airflow surfaces.

## Celery — `apply_when_clean`

Schedule a task for the next clean window using Celery's own `countdown` — **no worker
is blocked** while waiting:

```python
from carbon_mesh.integrations.celery import apply_when_clean

apply_when_clean(train_model, "aws/us-east-1", args=(dataset,), max_intensity=150)
```

If the grid is clean now it dispatches immediately; otherwise it schedules the task
for the soonest cleaner/surplus window (capped at `max_wait_hours`). No Celery import
is needed — it just calls your task's `.apply_async`.

### Feeding org-statement

Pass `report=True` to any of these wrappers (`apply_when_clean`, `wait_for_clean_window`,
`clean_window_op`) to POST each deferral's predicted impact to the API's org ledger,
best-effort — so Celery/Prefect/Dagster jobs accrue into `org-statement` and the
Prometheus impact gauges the same way `carbonlens run --report-to` does. A reporting
failure never blocks the job. The predicted reduction is per-kWh (energy is unknown at
schedule time); real grams still need a metered run via `carbonlens run --measure-energy`.
