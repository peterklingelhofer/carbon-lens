"""Tests for the carbon-aware Python SDK (pure decision logic + the wait loop)."""

from carbon_mesh.sdk import CarbonClient, choose_by_carbon, choose_by_state, is_good_time


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
