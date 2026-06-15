# Contributing

Thanks for taking a look. This is a portfolio project, but it's built to real
standards — the gates below run in CI and locally via git hooks.

## Setup

```bash
make setup          # uv sync, git hooks, .env, frontend build
# or manually:
uv sync --all-extras
cd web && npm install
```

Run it:

```bash
make dev            # API (:8000) + frontend (:5173) with hot reload
```

The API runs fully offline with no keys (`CARBON_LENS_CARBON_SOURCE=mock`), or with
the `hybrid` cascade and whatever provider keys are in `.env`. See the README's
"Adding Credentials" for the free keys.

## The workflow: typecheck → test → lint

Before opening a PR, everything below must pass (CI enforces it):

```bash
# Backend
uv run pyright src                 # types
CARBON_LENS_CARBON_SOURCE=mock uv run pytest tests/ -q
uv run ruff check src tests && uv run ruff format --check src

# Frontend (in web/)
npx tsc -b
npm run test                       # vitest
npx biome check .

# Or the shortcuts:
make lint                          # ruff + biome + tsc
make fix                           # auto-fix ruff + biome
```

Two things CI also checks, so regenerate them when you touch routes or the API
shape:

```bash
make openapi                       # rebuild openapi.json + web/src/api/schema.ts
```

CI fails if the committed `openapi.json` or generated `schema.ts` drift from the
live app — keeping the spec and the typed client honest.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), enforced by a
commit-msg hook (commitlint). Title only, no body, lowercase subject:

```
feat(carbon): add Taipower per-unit fuel mix parser
fix(web): stop scheduler code blocks overflowing on mobile
test(sla): cover the repository round-trip
```

Valid types: `feat fix docs style refactor perf test build ci chore revert`.

## How to add a carbon data source

1. Create `src/carbon_mesh/carbon_sources/<name>.py` that produces a
   `CarbonIntensity` — ideally by building a normalized fuel mix and passing it
   through `emission_factors` (`calculate_carbon_intensity`,
   `calculate_renewable_percentage`, `calculate_marginal_intensity`,
   `power_breakdown`) so you get intensity, renewable %, marginal, and the
   breakdown for free.
2. Declare its zones and slot it into the cascade in
   [`hybrid.py`](src/carbon_mesh/carbon_sources/hybrid.py) at the right priority.
3. Add a **fixture parse test** in `tests/test_parsers.py` against a small sample of
   the real upstream format — this is what catches upstream format drift in CI
   before a zone silently goes dark.
4. Parse any XML with `defusedxml`, never the stdlib parser.

## How to add a region / provider

Add it to [`data/region_grid_map.yaml`](data/region_grid_map.yaml) under the
provider, mapping it to an existing `grid_zone` (so it inherits carbon coverage).
US regions also take `eia_respondent` / `gridstatus_iso`. New providers that reuse
existing zones need no new integration — see how Scaleway/OVH/Hetzner were added.

## Principles

- **Label every estimate.** Never present a heuristic or fallback as measured data.
- **Snapshot, don't hammer.** User-facing reads come from the published snapshot,
  not live provider calls — keep quota cost `O(zones × cadence)`.
- **Keep the spec and client in sync** via `make openapi`.
- Simplicity first; minimal footprint; find root causes, not band-aids.
