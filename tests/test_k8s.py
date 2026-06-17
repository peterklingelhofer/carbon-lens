"""Tests for the carbon-aware CronJob suspend controller's pure decision logic."""

from datetime import datetime, timezone

from carbon_mesh.k8s.carbon_suspend import (
    ANNOTATION_MAX_DEFER,
    ANNOTATION_MAX_INTENSITY,
    ANNOTATION_REGION,
    desired_suspend_change,
    overdue,
    should_suspend,
    _hours_since,
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


def test_overdue_backstop():
    assert overdue(13, 12) is True
    assert overdue(5, 12) is False
    assert overdue(None, 12) is False  # unknown last-run -> don't force
    assert overdue(100, None) is False  # no deadline set -> never force


def test_deadline_forces_run_despite_dirty_grid():
    ann = {ANNOTATION_REGION: "aws/us-east-1", ANNOTATION_MAX_DEFER: "12"}
    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False}
    # Suspended and only 3h since last run -> stay suspended.
    assert desired_suspend_change(ann, True, dirty, hours_since_run=3) is None
    # Suspended and 13h since last run (past the 12h deadline) -> force resume.
    assert desired_suspend_change(ann, True, dirty, hours_since_run=13) is False


def test_hours_since_parses_rfc3339():
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    assert _hours_since("2026-06-16T06:00:00Z", now) == 6.0
    assert _hours_since(None, now) is None
    assert _hours_since("garbage", now) is None
