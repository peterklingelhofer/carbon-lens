"""Guard test for the minimal dispatcher example's decision logic."""

import importlib.util


def _load():
    spec = importlib.util.spec_from_file_location(
        "dispatch_example", "examples/dispatcher/dispatch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decide_run_and_wait():
    decide = _load().decide
    run = decide({"advice": "run_now", "clean_surplus": False})
    assert run["action"] == "run"

    surplus = decide({"advice": "wait_for_cleaner", "clean_surplus": True})
    assert surplus["action"] == "run" and "surplus" in surplus["reason"]

    wait = decide(
        {"advice": "wait_for_cleaner", "clean_surplus": False, "surplus_window_in_hours": 4}
    )
    assert wait["action"] == "wait" and wait["wait_hours"] == 4
