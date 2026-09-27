# Minimal carbon-aware dispatcher

Polls this API's `/carbon/signal` for one region and decides **run vs wait**,
honouring clean surplus and an optional intensity cap. It re-checks every ten minutes
and exits once the answer is run, so it can sit in front of a flexible job in cron.

```bash
uv run python examples/dispatcher/dispatch.py aws/us-east-1   # or zone/FR for on-prem
```

`decide(signal, max_intensity)` is pure and returns `{action, reason, wait_hours}`.
It depends only on the **stable `/carbon/signal` contract** (`state`, `advice`,
`clean_surplus`, `surplus_window_in_hours`, `marginal_basis`), which
[`tests/test_signal_contract.py`](../../tests/test_signal_contract.py) guards.
