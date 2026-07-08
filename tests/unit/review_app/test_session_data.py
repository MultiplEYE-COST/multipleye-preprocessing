"""Tests for session data service."""

from review_app.services.session_data import (
    read_overview,
    compute_checks,
    _is_checkable,
    CHECK_REGISTRY,
)
from pathlib import Path


def test_read_overview_missing(tmp_path: Path) -> None:
    result = read_overview(tmp_path / "nonexistent.yaml")
    assert result is None


def test_read_overview_valid(tmp_path: Path) -> None:
    yaml_path = tmp_path / "test.yaml"
    yaml_path.write_text("num_calibrations: 11\ndata_loss_ratio: 0.02\n")
    result = read_overview(yaml_path)
    assert result == {"num_calibrations": 11, "data_loss_ratio": 0.02}


def test_compute_checks_with_thresholds() -> None:
    overview = {
        "num_calibrations": 11,
        "num_validations": 7,
        "data_loss_ratio": 0.02,
    }
    thresholds = {
        "num_calibrations": [3, 30],
        "num_validations": [13, 30],
        "data_loss_ratio": [0.0, 0.1],
    }
    checks = compute_checks(overview, thresholds)
    check_map = {c.check_id: c for c in checks}

    assert check_map["num_calibrations"].status == "pass"
    assert check_map["num_validations"].status == "fail"
    assert check_map["data_loss_ratio"].status == "pass"


def test_compute_checks_skips_non_checkable() -> None:
    overview = {
        "tracked_eye": "R",
        "Mount_configuration": {"mount_type": "Desktop"},
    }
    thresholds = {}
    checks = compute_checks(overview, thresholds)
    check_ids = {c.check_id for c in checks}
    assert "tracked_eye" in check_ids
    assert "Mount_configuration" not in check_ids


def test_compute_checks_without_thresholds() -> None:
    overview = {"num_calibrations": 11, "num_validations": 7}
    checks = compute_checks(overview, None)
    for c in checks:
        assert c.status == "pass"


def test_is_checkable() -> None:
    assert _is_checkable(5)
    assert _is_checkable(3.14)
    assert _is_checkable(True)
    assert _is_checkable("hello")
    assert not _is_checkable({"a": 1})
    assert not _is_checkable([1, 2])
    assert not _is_checkable(None)


def test_check_registry_covers_expected_fields() -> None:
    fields = {e["field"] for e in CHECK_REGISTRY}
    assert "num_calibrations" in fields
    assert "num_validations" in fields
    assert "avg_validation_error" in fields
    assert "data_loss_ratio" in fields
    assert "tracked_eye" in fields
    assert "tracked_eye_consistent" in fields
    assert "avg_comprehension_score" in fields
    assert "total_session_duration" in fields
    assert "num_completed_trials" in fields


def test_compute_checks_num_completed_trials_pass() -> None:
    overview = {"num_completed_trials": 12}
    thresholds = {"num_completed_trials": [6, 12]}
    checks = compute_checks(overview, thresholds)
    check_map = {c.check_id: c for c in checks}
    assert check_map["num_completed_trials"].status == "pass"
    assert check_map["num_completed_trials"].value == 12
    assert check_map["num_completed_trials"].threshold == [6.0, 12.0]


def test_compute_checks_num_completed_trials_fail() -> None:
    overview = {"num_completed_trials": 4}
    thresholds = {"num_completed_trials": [6, 12]}
    checks = compute_checks(overview, thresholds)
    check_map = {c.check_id: c for c in checks}
    assert check_map["num_completed_trials"].status == "fail"
    assert check_map["num_completed_trials"].value == 4


def test_compute_checks_scalar_threshold_does_not_crash() -> None:
    """Regression: scalar thresholds (e.g. ``num_completed_trials: 6`` in a
    legacy ``quality_thresholds.yaml``) must be serialized as ``"6"`` (str)
    not ``6`` (int). ``CheckResult.threshold`` accepts ``str | list | None``
    — a bare ``int`` would crash pydantic and propagate up through
    ``list_sessions()`` → ``_build_dcn_summary()`` → ``list_dcns()``,
    blanking the entire home page.

    This test covers the code path where ``threshold_spec`` from
    ``check_value()`` is a scalar int/float. The comparison semantics
    (scalar = upper bound) are tested in ``test_thresholds.py``.
    """
    overview = {
        "data_loss_ratio": 0.02,
        "num_practice_trials": 2,
    }
    thresholds = {
        "data_loss_ratio": 0.1,
        "num_practice_trials": 2,
    }
    checks = compute_checks(overview, thresholds)
    check_map = {c.check_id: c for c in checks}

    assert check_map["data_loss_ratio"].status == "pass"
    assert check_map["data_loss_ratio"].threshold == "0.1"

    assert check_map["num_practice_trials"].status == "pass"
    assert check_map["num_practice_trials"].threshold == "2"
