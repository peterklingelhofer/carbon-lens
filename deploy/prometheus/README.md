# Prometheus + Alertmanager for CarbonLens

CarbonLens exposes gauges at `/metrics`, refreshed on each scrape (see
`src/carbon_mesh/api/metrics.py`). This directory wires alerting on top of them.

| File | Purpose |
| --- | --- |
| [`carbonlens.rules.yml`](carbonlens.rules.yml) | Prometheus alert rules |
| [`alertmanager.example.yml`](alertmanager.example.yml) | Example routing by severity |
| [`RUNBOOK.md`](RUNBOOK.md) | What each alert means and how to fix it |

## Wire it up

In `prometheus.yml`:

```yaml
rule_files:
  - /etc/prometheus/carbonlens.rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: carbonlens
    metrics_path: /metrics
    static_configs:
      - targets: ["carbonlens:8000"]
```

Run Alertmanager with `--config.file=alertmanager.example.yml` (after pointing its
receivers at your real pager/Slack/email). The Grafana dashboard in
[`../../grafana/carbonlens-dashboard.json`](../../grafana/carbonlens-dashboard.json)
visualises the same gauges, including the `carbon_marginal_unmapped` honesty panel.
