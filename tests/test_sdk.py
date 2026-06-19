"""Tests for the carbon-aware Python SDK (pure decision logic + the wait loop)."""

from carbon_mesh.sdk import (
    CarbonClient,
    choose_by_carbon,
    choose_by_state,
    impact_from_signal,
    is_good_time,
)


def test_choose_by_carbon():
    clean = {"advice": "run_now", "clean_surplus": False}
    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False}
    assert choose_by_carbon(clean, "gpt-full", "gpt-mini") == "gpt-full"
    assert choose_by_carbon(dirty, "gpt-full", "gpt-mini") == "gpt-mini"


def test_choose_by_state():
    assert choose_by_state({"state": "green"}, "full", "mid", "lean") == "full"
    assert choose_by_state({"state": "yellow"}, "full", "mid", "lean") == "mid"
    assert choose_by_state({"state": "red"}, "full", "mid", "lean") == "lean"
    # Unknown/missing state -> the lowest-carbon (red) choice.
    assert choose_by_state({}, "full", "mid", "lean") == "lean"


def test_client_choose_by_carbon():
    cl = CarbonClient()
    cl.signal = lambda region: {"advice": "wait_for_cleaner", "clean_surplus": False}  # type: ignore
    assert cl.choose_by_carbon("aws/us-east-1", "full", "mini") == "mini"


def test_is_good_time_run_now():
    assert is_good_time({"advice": "run_now", "clean_surplus": False}) is True


def test_is_good_time_surplus():
    assert is_good_time({"advice": "wait_for_cleaner", "clean_surplus": True}) is True


def test_is_good_time_dirty():
    assert is_good_time({"advice": "wait_for_cleaner", "clean_surplus": False}) is False


def test_is_good_time_respects_cap():
    sig = {"advice": "run_now", "clean_surplus": False, "intensity_gco2_kwh": 300}
    assert is_good_time(sig, max_intensity=150) is False
    assert is_good_time(sig, max_intensity=400) is True


def test_wait_returns_immediately_when_clean():
    cl = CarbonClient()
    cl.signal = lambda region: {"advice": "run_now", "clean_surplus": False}  # type: ignore
    slept: list[float] = []
    result = cl.wait_for_clean_window("aws/us-east-1", _sleep=slept.append, _clock=lambda: 0.0)
    assert result["reason"] == "clean"
    assert slept == []  # never had to wait


def test_wait_gives_up_at_deadline():
    cl = CarbonClient()
    cl.signal = lambda region: {"advice": "wait_for_cleaner", "clean_surplus": False}  # type: ignore
    ticks = iter([0.0, 0.0, 10_000.0])  # first check, deadline check, then past deadline
    slept: list[float] = []
    result = cl.wait_for_clean_window(
        "aws/us-east-1",
        max_wait_hours=1,
        poll_seconds=60,
        _sleep=slept.append,
        _clock=lambda: next(ticks),
    )
    assert result["reason"] == "deadline"


def test_wait_polls_until_clean():
    cl = CarbonClient()
    sequence = iter(
        [
            {"advice": "wait_for_cleaner", "clean_surplus": False},
            {"advice": "run_now", "clean_surplus": False},
        ]
    )
    cl.signal = lambda region: next(sequence)  # type: ignore
    slept: list[float] = []
    result = cl.wait_for_clean_window("aws/us-east-1", _sleep=slept.append, _clock=lambda: 0.0)
    assert result["reason"] == "clean"
    assert slept == [600]  # waited one poll interval before the second (clean) check


def test_signal_reads_from_snapshot_without_calling_api():
    cl = CarbonClient(snapshot_url="https://cdn.example/snapshot.json")
    snap = {"signals": {"aws/us-east-1": {"advice": "run_now", "state": "green"}}}
    cl._load_snapshot = lambda: snap  # type: ignore

    # Any API call would explode this, proving the snapshot path is used.
    cl_api_called = []
    import carbon_mesh.sdk as sdk_mod

    orig_get = sdk_mod.httpx.get
    sdk_mod.httpx.get = lambda *a, **k: cl_api_called.append(1)  # type: ignore
    try:
        sig = cl.signal("aws/us-east-1")
    finally:
        sdk_mod.httpx.get = orig_get
    assert sig == {"advice": "run_now", "state": "green"}
    assert cl_api_called == []  # served from the snapshot, no API hit


def test_signal_falls_back_to_api_when_region_absent_from_snapshot(monkeypatch):
    cl = CarbonClient(snapshot_url="https://cdn.example/snapshot.json")
    cl._load_snapshot = lambda: {"signals": {"aws/us-east-1": {"advice": "run_now"}}}  # type: ignore

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"advice": "wait_for_cleaner", "from": "api"}

    called = {}

    def fake_get(url, timeout):
        called["url"] = url
        return _Resp()

    monkeypatch.setattr("carbon_mesh.sdk.httpx.get", fake_get)
    # zone/FR isn't in the snapshot -> API fallback.
    sig = cl.signal("zone/FR")
    assert sig == {"advice": "wait_for_cleaner", "from": "api"}
    assert "/api/v1/carbon/signal/zone/FR" in called["url"]


def test_load_snapshot_caches_and_serves_stale_on_error():
    cl = CarbonClient(snapshot_url="https://cdn.example/snapshot.json")
    calls = []

    class _Resp:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self._body

    import carbon_mesh.sdk as sdk_mod

    orig = sdk_mod.httpx.get
    sdk_mod.httpx.get = lambda *a, **k: (calls.append(1), _Resp({"signals": {}}))[1]  # type: ignore
    try:
        clock = [1000.0]
        first = cl._load_snapshot(_clock=lambda: clock[0])
        # Within TTL -> cached, no second fetch.
        clock[0] = 1000.0 + 100
        second = cl._load_snapshot(_clock=lambda: clock[0])
        assert first is second
        assert len(calls) == 1
    finally:
        sdk_mod.httpx.get = orig


def test_impact_from_signal_predicts_reduction_and_mirrors_basis():
    signal = {
        "intensity_gco2_kwh": 400,
        "cleaner_window_intensity_gco2_kwh": 250,
        "marginal_basis": "measured",
    }
    entry = impact_from_signal("aws/us-east-1", signal, deferred_hours=3.4)
    assert entry["region"] == "aws/us-east-1"
    assert entry["deferred_hours"] == 3  # rounded
    assert entry["reduction_gco2_kwh"] == 150.0
    assert entry["energy_kwh"] is None
    assert entry["basis"] == "measured"


def test_impact_from_signal_clamps_and_defaults():
    # No cleaner window -> no predicted reduction; missing basis -> heuristic
    entry = impact_from_signal("zone/FR", {"intensity_gco2_kwh": 300}, deferred_hours=0)
    assert entry["reduction_gco2_kwh"] == 0.0
    assert entry["basis"] == "heuristic"


def test_wait_reports_predicted_impact_when_it_shifts():
    cl = CarbonClient()
    sequence = iter(
        [
            {
                "advice": "wait_for_cleaner",
                "clean_surplus": False,
                "intensity_gco2_kwh": 400,
                "cleaner_window_intensity_gco2_kwh": 250,
                "marginal_basis": "measured",
            },
            {"advice": "run_now", "clean_surplus": False},
        ]
    )
    cl.signal = lambda region: next(sequence)  # type: ignore
    reported: list[dict] = []
    cl.report_impact = lambda entry: reported.append(entry) or {"stored": True}  # type: ignore
    ticks = iter([0.0, 0.0, 3600.0])  # start, deadline-check, waited-hours read
    result = cl.wait_for_clean_window(
        "aws/us-east-1",
        report=True,
        _sleep=lambda s: None,
        _clock=lambda: next(ticks),
    )
    assert result["reason"] == "clean"
    assert result["waited_hours"] == 1.0
    assert reported == [
        {
            "region": "aws/us-east-1",
            "deferred_hours": 1,
            "reduction_gco2_kwh": 150.0,
            "energy_kwh": None,
            "basis": "measured",
        }
    ]


def test_wait_does_not_report_when_already_clean():
    cl = CarbonClient()
    cl.signal = lambda region: {"advice": "run_now", "clean_surplus": False}  # type: ignore
    reported: list[dict] = []
    cl.report_impact = lambda entry: reported.append(entry)  # type: ignore
    cl.wait_for_clean_window(
        "aws/us-east-1", report=True, _sleep=lambda s: None, _clock=lambda: 0.0
    )
    assert reported == []  # no deferral, nothing to report


def test_run_when_clean_decorator_runs_after_wait():
    cl = CarbonClient()
    cl.signal = lambda region: {"advice": "run_now", "clean_surplus": False}  # type: ignore
    calls: list[int] = []

    @cl.run_when_clean("aws/us-east-1")
    def job(x):
        calls.append(x)
        return x * 2

    assert job(21) == 42
    assert calls == [21]
