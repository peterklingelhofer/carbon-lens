"""Tests for the carbon-aware CronJob suspend controller's pure decision logic."""

from carbon_mesh.k8s.carbon_suspend import (
    ANNOTATION_MAX_INTENSITY,
    ANNOTATION_REGION,
    desired_suspend_change,
    should_suspend,
    _signal_path,
)


def test_should_suspend_run_now_keeps_running():
    assert should_suspend({"advice": "run_now", "clean_surplus": False}) is False


def test_should_suspend_surplus_keeps_running():
    assert should_suspend({"advice": "wait_for_cleaner", "clean_surplus": True}) is False


def test_should_suspend_when_dirty():
    assert should_suspend({"advice": "wait_for_cleaner", "clean_surplus": False}) is True


def test_max_intensity_cap_overrides_run_now():
    # run_now but over the caller's cap -> still suspend.
    signal = {"advice": "run_now", "clean_surplus": False, "intensity_gco2_kwh": 300}
    assert should_suspend(signal, max_intensity=150) is True
    assert should_suspend(signal, max_intensity=400) is False


def test_desired_change_only_when_it_differs():
    ann = {ANNOTATION_REGION: "aws/us-east-1"}
    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False}
    # Currently running, grid dirty -> should become suspended.
    assert desired_suspend_change(ann, current_suspend=False, signal=dirty) is True
    # Already suspended -> no change needed.
    assert desired_suspend_change(ann, current_suspend=True, signal=dirty) is None


def test_unmanaged_cronjob_is_ignored():
    assert desired_suspend_change({}, current_suspend=False, signal={"advice": "run_now"}) is None


def test_max_intensity_annotation_is_honored():
    ann = {ANNOTATION_REGION: "aws/us-east-1", ANNOTATION_MAX_INTENSITY: "150"}
    signal = {"advice": "run_now", "clean_surplus": False, "intensity_gco2_kwh": 300}
    # Over the annotated cap while running -> should suspend.
    assert desired_suspend_change(ann, current_suspend=False, signal=signal) is True


def test_signal_path_handles_zones_and_regions():
    assert _signal_path("aws/us-east-1") == "/api/v1/carbon/signal/aws/us-east-1"
    assert _signal_path("zone/FR") == "/api/v1/carbon/signal/zone/FR"
