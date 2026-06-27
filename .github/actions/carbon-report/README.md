# CarbonLens Clean-Compute Report Action

Surface the **State of Clean Compute** report in your own CI — as a job summary, and
optionally a PR comment. The report (greenest regions to deploy, where carbon-aware
scheduling helps most) is published every ~30 min from real grid history, so this is
a zero-cost read.

## Usage

As a job summary on any workflow:

```yaml
- uses: peterklingelhofer/carbon-lens/.github/actions/carbon-report@main
```

Post it as a PR comment (e.g. on infra PRs, to nudge region choice):

```yaml
permissions:
  pull-requests: write
jobs:
  carbon:
    runs-on: ubuntu-latest
    steps:
      - uses: peterklingelhofer/carbon-lens/.github/actions/carbon-report@main
        with:
          comment: "true"
        env:
          GH_TOKEN: ${{ github.token }}
```

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `report-url` | public data branch | URL of the published `clean_compute_report.json`. Point at your own deployment if you publish one. |
| `top` | `8` | Rows per table. |
| `comment` | `false` | Also post a PR comment (needs `pull-requests: write` and `GH_TOKEN`). |

It degrades gracefully: if the report can't be fetched it emits a warning and exits 0,
never failing your build.
