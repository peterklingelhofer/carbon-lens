# CarbonLens Carbon Signal Action

Check whether *now* is a low-carbon time to run a workflow, with an honest
marginal/surplus read from the live grid. Use it to **gate or annotate** jobs so
flexible work runs when the grid is cleanest.

It calls `/carbon/signal` and surfaces the same intelligence as the rest of
CarbonLens: the average traffic light, the **marginal** intensity (what an extra
kWh actually emits — the number that responds to shifting load), and whether the
grid is in **clean surplus** (renewables abundant, the highest-value time to run).

## Usage

Annotate every run (advisory, never fails):

```yaml
- uses: peterklingelhofer/carbonlens/.github/actions/carbon-signal@main
  with:
    region: aws/us-east-1
```

Gate a non-urgent job — skip when the grid is dirty and let the next cron run retry:

```yaml
on:
  schedule:
    - cron: "0 * * * *" # hourly; reruns until a clean window
jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - id: carbon
        uses: peterklingelhofer/carbonlens/.github/actions/carbon-signal@main
        with:
          region: aws/us-east-1
          max-intensity: "150"
          fail-if-dirty: "true" # step exits 1 when it isn't a good time
      - run: ./train.sh # only reached when the grid is clean enough
```

Branch on the output instead of failing:

```yaml
- id: carbon
  uses: peterklingelhofer/carbonlens/.github/actions/carbon-signal@main
  with: { region: aws/us-east-1 }
- if: steps.carbon.outputs.clean-now == 'true'
  run: ./deploy.sh
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `region` | yes | — | `provider/region`, e.g. `aws/us-east-1`. For a self-hosted runner, use the region it actually runs in. |
| `api-url` | no | public instance | CarbonLens API base URL. |
| `max-intensity` | no | — | gCO2/kWh cap; "now" counts as clean only at/under this. |
| `fail-if-dirty` | no | `false` | Exit 1 when now isn't a good time, so a cron workflow skips and reruns later. |

## Outputs

`clean-now`, `state`, `advice`, `intensity`, `marginal`, `clean-surplus`,
`surplus-window-hours`.

## Honest limits

This shifts carbon only for genuinely flexible work, and GitHub's own constraints
matter:

- **Hosted runners run in a fixed region you can't choose**, and you can't cheaply
  pause one mid-run. So the real wins are: **cron-triggered / non-urgent workflows**
  where skipping and rerunning later is fine, **self-hosted runners** (set `region`
  to where they live), and **advisory annotations** that build awareness.
- The signal is marginal-*estimated* (a fuel-mix heuristic), not measured marginal
  data, and surplus is inferred, not metered curtailment. It will tell you when
  shifting **won't** help (fossil on the margin either way) rather than always
  flashing green.
