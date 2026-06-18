# Minimal carbon-aware dispatcher

The loosely-coupled pattern the companion `carbon-aware-dispatcher` follows: poll
`/carbon/signal`, decide **run vs wait**, honouring clean surplus and an optional
intensity cap. Run it as a sidecar or cron before a flexible job.

```bash
uv run python examples/dispatcher/dispatch.py aws/us-east-1   # or zone/FR for on-prem
```

`decide(signal, max_intensity)` is pure and returns `{action, reason, wait_hours}`.
It depends only on the **stable `/carbon/signal` contract** — `state`, `advice`,
`clean_surplus`, `surplus_window_in_hours`, `marginal_basis` — which
[`tests/test_signal_contract.py`](../../tests/test_signal_contract.py) guards, so the
two repos stay honest against each other without sharing internals.
